from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from uuid import uuid4


class User(models.Model):
    user_id = models.UUIDField(default=uuid4, editable=False)
    username = models.CharField(max_length=50)
    email = models.EmailField(max_length=254)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Call the real save() method
        Wallet.objects.get_or_create(user=self)


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.user.username}'s Wallet - {self.balance} "


class Expense(models.Model):
    transaction_id = models.UUIDField(default=uuid4, editable=False)
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=50, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.paid_by.username} paid {self.amount} - {self.transaction_id}"

    def save(self, *args, **kwargs):
        wallet = Wallet.objects.get(user=self.paid_by)
        if wallet.balance < self.amount:
            raise ValueError('Insufficient funds')
        wallet.balance -= self.amount
        wallet.save()

        super().save(*args, **kwargs)  # Call the real save() method


class ExpenseSharing(models.Model):
    EQUAL = 'EQUAL'
    EXACT = 'EXACT'
    PERCENT = 'PERCENT'
    EXPENSE_TYPE_CHOICES = [
        (EQUAL, 'EQUAL'),
        (EXACT, 'EXACT'),
        (PERCENT, 'PERCENT'),
    ]

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE)
    method = models.CharField(choices=EXPENSE_TYPE_CHOICES, max_length=50)
    split_with = models.ManyToManyField(User)
    # note. you'll trim before you split if multiple
    values = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f" {self.expense.paid_by} split {self.expense.amount} "

    @property
    def shared_value(self):
        split_value = {}
        paid_by = self.expense.paid_by.username
        paid_by_wallet = Wallet.objects.get(user=self.expense.paid_by)
        users = self.split_with.all()

        if self.method == 'EQUAL':
            # Calculate the split amount
            split_amount = self.expense.amount / Decimal(users.count() + 1)

            # First pass: Set split_value for all users
            for user in users:
                if user.username not in split_value:
                    split_value[user.username] = {}
                split_value[user.username][paid_by] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes {paid_by} : {split_amount}"
                }

                # set value for paid_by
                if paid_by not in split_value:
                    split_value[paid_by] = {}
                split_value[paid_by][user.username] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes : {split_amount}"
                }

        elif self.method == 'EXACT':
            # Calculate the split amount
            exact_split_amounts = [
                Decimal(value) for value in self.values.replace(" ", "").split(',')]
            if len(exact_split_amounts) != len(users):
                raise ValueError(
                    'Please check the your selected users or the values')

            for i, user in enumerate(users):
                # assign the amount to its owner/user
                split_amount = exact_split_amounts[i]

                # check if the user/paid_by is in the split value dictionary
                if user.username not in split_value:
                    split_value[user.username] = {}
                if paid_by not in split_value:
                    split_value[paid_by] = {}

                # set values for user and paid_by
                split_value[user.username][paid_by] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes {paid_by} : {split_amount}"
                }
                split_value[paid_by][user.username] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes {paid_by} : {split_amount}"
                }

        elif self.method == 'PERCENT':
            amount = self.expense.amount
            split_amounts = [
                Decimal(value)/100*amount for value in self.values.replace(" ", "").split(',')]

            if len(split_amounts) != len(users):
                raise ValueError(
                    'Please check the your selected users or the values')

            for i, user in enumerate(users):
                split_amount = split_amounts[i]
                if user.username not in split_value:
                    split_value[user.username] = {}
                if paid_by not in split_value:
                    split_value[paid_by] = {}

                split_value[user.username][paid_by] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes {paid_by} : {split_amount}"
                }
                split_value[paid_by][user.username] = {
                    'split_amount': split_amount,
                    'status': 'Unpaid',
                    'summary': f"{user.username} owes {paid_by} : {split_amount}"
                }

        for user in users:
            # get and verify wallet balance
            wallet = Wallet.objects.get(user=user)
            if wallet.balance >= Decimal(split_amount):
                wallet.balance -= Decimal(split_amount)
                wallet.save()

                paid_by_wallet.balance += Decimal(split_amount)
                paid_by_wallet.save()

                split_value[user.username][paid_by]['status'] = 'Paid'
                split_value[user.username][paid_by]['summary'] = f"{
                    user.username} Paid {paid_by} : {split_amount}"
                split_value[paid_by][user.username]['status'] = 'Paid'
                split_value[paid_by][user.username]['summary'] = f"{
                    user.username} Paid : {split_amount}"

        return split_value
