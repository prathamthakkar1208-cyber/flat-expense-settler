from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "add-expense/",
        views.add_expense,
        name="add_expense",
    ),

    path(
        "settle-up/",
        views.settle_up,
        name="settle_up",
    ),
]