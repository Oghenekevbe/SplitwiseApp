from django.contrib import admin
from .models import User, Expense, Wallet, ExpenseSharing

# Register your models here.
admin.site.register(User)
admin.site.register(Wallet)
admin.site.register(Expense)
admin.site.register(ExpenseSharing)
