from django.contrib import admin
from .models import Person, Expense, ExpenseShare, Settlement

admin.site.register(Person)
admin.site.register(Expense)
admin.site.register(ExpenseShare)
admin.site.register(Settlement)
# Register your models here.
