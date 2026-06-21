from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Company, Reward, User


class BootstrapFormMixin:
    """Добавляет класс form-control / form-select / form-check-input всем полям формы."""

    def _apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')


class CompanyRegistrationForm(BootstrapFormMixin, forms.Form):
    """Регистрация компании + первого администратора."""

    company_name = forms.CharField(label='Название компании', max_length=255)
    subscription_plan = forms.ChoiceField(label='Тарифный план', choices=Company.PLAN_CHOICES, initial='rostok')

    first_name = forms.CharField(label='Имя', max_length=150)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторите пароль', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже зарегистрирован.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Пароли не совпадают.')
        return cleaned


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """Форма входа по email вместо username."""

    username = forms.EmailField(label='Email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_username(self):
        return self.cleaned_data['username'].lower().strip()


class GiveCoinsForm(BootstrapFormMixin, forms.Form):
    """Форма отправки «Спасибо» коллеге."""

    to_user = forms.ModelChoiceField(
        label='Кому', queryset=User.objects.none(), empty_label='Выберите коллегу'
    )
    amount = forms.IntegerField(label='Количество монет', min_value=1)
    comment = forms.CharField(
        label='Сообщение', widget=forms.Textarea(attrs={'rows': 3}), required=False
    )

    def __init__(self, *args, sender=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender = sender
        if sender is not None:
            self.fields['to_user'].queryset = (
                User.objects.filter(company=sender.company).exclude(pk=sender.pk)
            )
        self._apply_bootstrap()

    def clean_to_user(self):
        to_user = self.cleaned_data['to_user']
        if self.sender and to_user == self.sender:
            raise ValidationError('Нельзя отправить монеты самому себе.')
        return to_user


class RewardForm(BootstrapFormMixin, forms.ModelForm):
    """Форма создания/редактирования награды (для администратора)."""

    class Meta:
        model = Reward
        fields = ['name', 'description', 'price', 'category', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class GoalForm(BootstrapFormMixin, forms.ModelForm):
    """Форма выбора цели сотрудником."""

    class Meta:
        model = User
        fields = ['current_goal', 'target_reward']
        widgets = {
            'current_goal': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['target_reward'].queryset = Reward.objects.filter(company=company, is_active=True)
        self.fields['target_reward'].required = False
        self.fields['target_reward'].empty_label = 'Без выбранной награды'
        self._apply_bootstrap()


class ENPSResponseForm(BootstrapFormMixin, forms.Form):
    """Анонимная форма ответа на опрос eNPS."""

    score = forms.IntegerField(
        label='Насколько вероятно, что вы порекомендуете компанию как место работы? (0-10)',
        min_value=0, max_value=10,
    )
    comment = forms.CharField(label='Комментарий (необязательно)', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class EmployeeAddForm(BootstrapFormMixin, forms.Form):
    """Форма добавления одного сотрудника администратором."""

    first_name = forms.CharField(label='Имя', max_length=150)
    last_name  = forms.CharField(label='Фамилия', max_length=150, required=False)
    email      = forms.EmailField(label='Email')
    department = forms.CharField(label='Отдел', max_length=255, required=False)
    hire_date  = forms.DateField(
        label='Дата приёма', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    role = forms.ChoiceField(
        label='Роль', choices=[('employee', 'Сотрудник'), ('admin', 'Администратор / HR')]
    )
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput, min_length=6)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self._apply_bootstrap()

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return email


class EmployeeEditForm(BootstrapFormMixin, forms.ModelForm):
    """Форма редактирования сотрудника администратором."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'department', 'hire_date', 'role']
        widgets = {'hire_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self._apply_bootstrap()

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Этот email уже занят другим пользователем.')
        return email


class ProfileEditForm(BootstrapFormMixin, forms.Form):
    """Самостоятельное редактирование сотрудником своих данных."""

    first_name = forms.CharField(label='Имя', max_length=150)
    last_name  = forms.CharField(label='Фамилия', max_length=150, required=False)
    department = forms.CharField(label='Отдел', max_length=255, required=False)
    email      = forms.EmailField(label='Email')

    new_password  = forms.CharField(
        label='Новый пароль', required=False, widget=forms.PasswordInput,
        help_text='Оставьте пустым, если не хотите менять пароль',
    )
    new_password2 = forms.CharField(
        label='Повторите новый пароль', required=False, widget=forms.PasswordInput,
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        if instance and not self.is_bound:
            self.fields['first_name'].initial = instance.first_name
            self.fields['last_name'].initial  = instance.last_name
            self.fields['department'].initial = instance.department
            self.fields['email'].initial      = instance.email

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None)
        if qs.exists():
            raise forms.ValidationError('Этот email уже используется другим пользователем.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('new_password2')
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError('Пароли не совпадают.')
            if len(p1) < 6:
                raise forms.ValidationError('Пароль должен содержать минимум 6 символов.')
        return cleaned

    def save(self):
        user = self.instance
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.department = self.cleaned_data['department']
        user.email      = self.cleaned_data['email']
        user.username   = self.cleaned_data['email']  # username = email во всей платформе
        if self.cleaned_data.get('new_password'):
            user.set_password(self.cleaned_data['new_password'])
        user.save()
        return user
