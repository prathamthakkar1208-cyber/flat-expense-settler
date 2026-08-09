from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Expense, ExpenseShare, Person, Settlement


def money_to_paise(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Please enter a valid amount.")

    if amount <= 0:
        raise ValueError("Amount must be greater than ₹0.")

    return int(amount * 100)


def home(request):
    people = list(Person.objects.all().order_by("id"))

    balances = {
        person.id: 0
        for person in people
    }

    # Expenses
    for expense in Expense.objects.all():
        balances[expense.paid_by_id] += expense.amount_paise

        for share in expense.shares.all():
            balances[share.person_id] -= share.amount_paise

    # Settlements
    for settlement in Settlement.objects.all():
        balances[settlement.paid_by_id] += settlement.amount_paise
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


def add_person(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Please enter a name.")
            return render(
                request,
                "expenses/add_person.html"
            )

        if Person.objects.filter(name__iexact=name).exists():
            messages.error(
                request,
                "This person is already added."
            )
            return render(
                request,
                "expenses/add_person.html"
            )

        Person.objects.create(name=name)

        messages.success(
            request,
            f"{name} added successfully! ✅"
        )

        return redirect("home")

    return render(
        request,
        "expenses/add_person.html"
    )


def add_expense(request):
    people = list(Person.objects.all().order_by("id"))

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

        paid_by_id = request.POST.get("paid_by")
        expense_date = request.POST.get("expense_date")

        if not description:
            messages.error(
                request,
                "Please enter what the expense was for."
            )
            return redirect("add_expense")

        try:
            amount_paise = money_to_paise(amount)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("add_expense")

        paid_by = get_object_or_404(
            Person,
            id=paid_by_id
        )

        share_values = {}

        try:
            for person in people:
                share_values[person.id] = money_to_paise(
                    request.POST.get(
                        f"share_{person.id}",
                        "0"
                    )
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
        paid_by_id = request.POST.get("paid_by")
        paid_to_id = request.POST.get("paid_to")

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
            amount_paise = money_to_paise(amount)
        except ValueError as error:
            messages.error(request, str(error))
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