from django.db import models


class Person(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Used to send add/edit/delete expense notifications."
    )

    def __str__(self):
        return self.name


class Expense(models.Model):
    description = models.CharField(max_length=200)
    amount_paise = models.PositiveBigIntegerField()
    paid_by = models.ForeignKey(
        Person,
        on_delete=models.PROTECT
    )
    expense_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.description} - "
            f"₹{self.amount_paise / 100:.2f}"
        )


class ExpenseShare(models.Model):
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="shares"
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT
    )
    amount_paise = models.PositiveBigIntegerField()

    def __str__(self):
        return (
            f"{self.person.name} - "
            f"₹{self.amount_paise / 100:.2f}"
        )


class Settlement(models.Model):
    paid_by = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="settlements_paid"
    )
    paid_to = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="settlements_received"
    )
    amount_paise = models.PositiveBigIntegerField()
    settlement_date = models.DateField()
    note = models.CharField(
        max_length=200,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.paid_by.name} paid "
            f"₹{self.amount_paise / 100:.2f} "
            f"to {self.paid_to.name}"
        )