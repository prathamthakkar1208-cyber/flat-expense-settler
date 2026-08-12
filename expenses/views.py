from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Expense, ExpenseShare, Person, Settlement


# =========================
# MONEY HELPER
# =========================

def money_to_paise(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Please enter a valid amount.")

    if amount < 0:
        raise ValueError("Amount cannot be negative.")

    return int(amount * 100)


# =========================
# EMAIL HELPER
# =========================

def send_notification_email(subject, message):
    try:
        recipient = getattr(
            settings,
            "EXPENSE_NOTIFICATION_EMAIL",
            None
        )

        sender = getattr(
            settings,
            "DEFAULT_FROM_EMAIL",
            None
        )

        if not recipient:
            print("EMAIL ERROR: EXPENSE_NOTIFICATION_EMAIL is not configured.")
            return

        if not sender:
            print("EMAIL ERROR: DEFAULT_FROM_EMAIL is not configured.")
            return

        send_mail(
            subject,
            message,
            sender,
            [recipient],
            fail_silently=False,
        )

        print("EMAIL SENT SUCCESSFULLY")

    except Exception as error:
        print("EMAIL ERROR:", error)


# =========================
# HOME
# =========================

def home(request):

    people = list(
        Person.objects.all().order_by("id")
    )

    balances = {
        person.id: 0
        for person in people
    }

    # Expenses
    for expense in Expense.objects.all():

        if expense.paid_by_id in balances:
            balances[expense.paid_by_id] += expense.amount_paise

        for share in expense.shares.all():

            if share.person_id in balances:
                balances[share.person_id] -= share.amount_paise

    # Settlements
    for settlement in Settlement.objects.all():

        if settlement.paid_by_id in balances:
            balances[settlement.paid_by_id] += settlement.amount_paise

        if settlement.paid_to_id in balances:
            balances[settlement.paid_to_id] -= settlement.amount_paise

    balance_data = []

    for person in people:

        balance_paise = balances[person.id]

        balance_data.append({
            "name": person.name,
            "balance_paise": balance_paise,
            "balance_rupees": abs(balance_paise) / 100,
        })

    recent_expenses = list(
        Expense.objects
        .select_related("paid_by")
        .prefetch_related("shares__person")
        .order_by("-expense_date", "-created_at")[:20]
    )

    for expense in recent_expenses:
        expense.amount_rupees = expense.amount_paise / 100

    recent_settlements = list(
        Settlement.objects
        .select_related("paid_by", "paid_to")
        .order_by("-settlement_date", "-created_at")[:20]
    )

    for settlement in recent_settlements:
        settlement.amount_rupees = settlement.amount_paise / 100

    return render(
        request,
        "expenses/home.html",
        {
            "balance_data": balance_data,
            "recent_expenses": recent_expenses,
            "recent_settlements": recent_settlements,
        },
    )


# =========================
# ADD PERSON
# =========================

def add_person(request):

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        if not name:

            messages.error(
                request,
                "Please enter a name."
            )

            return render(
                request,
                "expenses/add_person.html"
            )

        if Person.objects.filter(
            name__iexact=name
        ).exists():

            messages.error(
                request,
                "This person is already added."
            )

            return render(
                request,
                "expenses/add_person.html"
            )

        Person.objects.create(
            name=name
        )

        messages.success(
            request,
            f"{name} added successfully! ✅"
        )

        return redirect("home")

    return render(
        request,
        "expenses/add_person.html"
    )


# =========================
# ADD EXPENSE
# =========================

def add_expense(request):

    people = list(
        Person.objects.all().order_by("id")
    )

    if len(people) < 2:

        messages.error(
            request,
            "Please add both flatmates before adding an expense."
        )

        return redirect("home")

    if request.method == "POST":

        description = request.POST.get(
            "description",
            ""
        ).strip()

        amount = request.POST.get(
            "amount",
            ""
        ).strip()

        paid_by_id = request.POST.get(
            "paid_by"
        )

        expense_date = request.POST.get(
            "expense_date"
        )

        if not description:

            messages.error(
                request,
                "Please enter what the expense was for."
            )

            return redirect("add_expense")

        try:

            amount_paise = money_to_paise(amount)

        except ValueError as error:

            messages.error(
                request,
                str(error)
            )

            return redirect("add_expense")

        if amount_paise <= 0:

            messages.error(
                request,
                "Amount must be greater than ₹0."
            )

            return redirect("add_expense")

        paid_by = get_object_or_404(
            Person,
            id=paid_by_id
        )

        share_values = {}

        try:

            for person in people:

                value = request.POST.get(
                    f"share_{person.id}",
                    "0"
                )

                share_values[person.id] = money_to_paise(
                    value
                )

        except ValueError:

            messages.error(
                request,
                "Please enter valid amounts for all shares."
            )

            return redirect("add_expense")

        if sum(share_values.values()) != amount_paise:

            messages.error(
                request,
                "The split amounts must add up exactly to the total expense."
            )

            return redirect("add_expense")

        if not expense_date:

            expense_date = timezone.localdate()

        with transaction.atomic():

            expense = Expense.objects.create(
                description=description,
                amount_paise=amount_paise,
                paid_by=paid_by,
                expense_date=expense_date,
            )

            for person in people:

                ExpenseShare.objects.create(
                    expense=expense,
                    person=person,
                    amount_paise=share_values[person.id],
                )

        # EMAIL
        send_notification_email(
            "💰 New Expense Added - Flat Expense Settler",
            f"""
A new expense has been added.

Expense: {description}
Amount: ₹{amount_paise / 100:.2f}
Paid by: {paid_by.name}
Date: {expense_date}

The expense has been successfully added.
"""
        )

        messages.success(
            request,
            "Expense added successfully! ✅"
        )

        return redirect("home")

    return render(
        request,
        "expenses/add_expense.html",
        {
            "people": people,
            "today": timezone.localdate().isoformat(),
        },
    )


# =========================
# EDIT EXPENSE
# =========================

def edit_expense(request, expense_id):

    expense = get_object_or_404(
        Expense,
        id=expense_id
    )

    people = list(
        Person.objects.all().order_by("id")
    )

    shares = {
        share.person_id: share.amount_paise
        for share in expense.shares.all()
    }

    share_data = []

    for person in people:

        amount_paise = shares.get(
            person.id,
            0
        )

        share_data.append({
            "person": person,
            "amount_rupees": f"{amount_paise / 100:.2f}",
        })

    if request.method == "POST":

        description = request.POST.get(
            "description",
            ""
        ).strip()

        amount = request.POST.get(
            "amount",
            ""
        ).strip()

        paid_by_id = request.POST.get(
            "paid_by"
        )

        expense_date = request.POST.get(
            "expense_date"
        )

        if not description:

            messages.error(
                request,
                "Please enter what the expense was for."
            )

            return redirect(
                "edit_expense",
                expense_id=expense.id
            )

        try:

            amount_paise = money_to_paise(amount)

        except ValueError as error:

            messages.error(
                request,
                str(error)
            )

            return redirect(
                "edit_expense",
                expense_id=expense.id
            )

        if amount_paise <= 0:

            messages.error(
                request,
                "Amount must be greater than ₹0."
            )

            return redirect(
                "edit_expense",
                expense_id=expense.id
            )

        paid_by = get_object_or_404(
            Person,
            id=paid_by_id
        )

        share_values = {}

        try:

            for person in people:

                value = request.POST.get(
                    f"share_{person.id}",
                    "0"
                )

                share_values[person.id] = money_to_paise(
                    value
                )

        except ValueError:

            messages.error(
                request,
                "Please enter valid amounts for all shares."
            )

            return redirect(
                "edit_expense",
                expense_id=expense.id
            )

        if sum(share_values.values()) != amount_paise:

            messages.error(
                request,
                "The split amounts must add up exactly to the total expense."
            )

            return redirect(
                "edit_expense",
                expense_id=expense.id
            )

        if not expense_date:

            expense_date = timezone.localdate()

        with transaction.atomic():

            expense.description = description
            expense.amount_paise = amount_paise
            expense.paid_by = paid_by
            expense.expense_date = expense_date

            expense.save()

            expense.shares.all().delete()

            for person in people:

                ExpenseShare.objects.create(
                    expense=expense,
                    person=person,
                    amount_paise=share_values[person.id],
                )

        # EMAIL
        send_notification_email(
            "✏️ Expense Updated - Flat Expense Settler",
            f"""
An expense has been updated.

Expense: {description}
Amount: ₹{amount_paise / 100:.2f}
Paid by: {paid_by.name}
Date: {expense_date}

The expense has been successfully updated.
"""
        )

        messages.success(
            request,
            "Expense updated successfully! ✅"
        )

        return redirect("home")

    return render(
        request,
        "expenses/edit_expense.html",
        {
            "expense": expense,
            "people": people,
            "share_data": share_data,
        },
    )


# =========================
# DELETE EXPENSE
# =========================

def delete_expense(request, expense_id):

    expense = get_object_or_404(
        Expense,
        id=expense_id
    )

    if request.method == "POST":

        description = expense.description
        amount = expense.amount_paise / 100
        paid_by = expense.paid_by.name

        expense.delete()

        # EMAIL
        send_notification_email(
            "🗑️ Expense Deleted - Flat Expense Settler",
            f"""
An expense has been deleted.

Expense: {description}
Amount: ₹{amount:.2f}
Paid by: {paid_by}

The expense has been successfully deleted.
"""
        )

        messages.success(
            request,
            "Expense deleted successfully! 🗑️"
        )

        return redirect("home")

    return render(
        request,
        "expenses/delete_expense.html",
        {
            "expense": expense,
        },
    )


# =========================
# SETTLE UP
# =========================

def settle_up(request):

    people = list(
        Person.objects.all().order_by("id")
    )

    if len(people) < 2:

        messages.error(
            request,
            "Please add both flatmates first."
        )

        return redirect("home")

    if request.method == "POST":

        paid_by_id = request.POST.get(
            "paid_by"
        )

        paid_to_id = request.POST.get(
            "paid_to"
        )

        amount = request.POST.get(
            "amount",
            ""
        ).strip()

        note = request.POST.get(
            "note",
            ""
        ).strip()

        if paid_by_id == paid_to_id:

            messages.error(
                request,
                "The person paying and receiving cannot be the same."
            )

            return redirect("settle_up")

        try:

            amount_paise = money_to_paise(
                amount
            )

        except ValueError as error:

            messages.error(
                request,
                str(error)
            )

            return redirect("settle_up")

        if amount_paise <= 0:

            messages.error(
                request,
                "Amount must be greater than ₹0."
            )

            return redirect("settle_up")

        paid_by = get_object_or_404(
            Person,
            id=paid_by_id
        )

        paid_to = get_object_or_404(
            Person,
            id=paid_to_id
        )

        Settlement.objects.create(
            paid_by=paid_by,
            paid_to=paid_to,
            amount_paise=amount_paise,
            settlement_date=timezone.localdate(),
            note=note,
        )

        # EMAIL
        send_notification_email(
            "💸 Settlement Recorded - Flat Expense Settler",
            f"""
A settlement has been recorded.

Paid by: {paid_by.name}
Paid to: {paid_to.name}
Amount: ₹{amount_paise / 100:.2f}
Date: {timezone.localdate()}
Note: {note if note else "No note"}

The settlement has been successfully recorded.
"""
        )

        messages.success(
            request,
            "Settlement recorded successfully! ✅"
        )

        return redirect("home")

    return render(
        request,
        "expenses/settle_up.html",
        {
            "people": people,
            "today": timezone.localdate().isoformat(),
        },
    )