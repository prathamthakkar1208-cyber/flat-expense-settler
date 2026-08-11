from django.urls import path

from . import views


urlpatterns = [

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "add-person/",
        views.add_person,
        name="add_person",
    ),

    path(
        "add-expense/",
        views.add_expense,
        name="add_expense",
    ),

    path(
        "edit-expense/<int:expense_id>/",
        views.edit_expense,
        name="edit_expense",
    ),

    path(
        "delete-expense/<int:expense_id>/",
        views.delete_expense,
        name="delete_expense",
    ),

    path(
        "settle-up/",
        views.settle_up,
        name="settle_up",
    ),

]