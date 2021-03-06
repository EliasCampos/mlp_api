import os
import io
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.mail import send_mail
from django.core.validators import MinLengthValidator, FileExtensionValidator
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.conf import settings
from PIL import Image
from userApp.manager import UserManager
from userApp.utils import (
    get_userpic_path,
    get_thumbnail_name,
    generate_random_string
)
from userApp.validators import MinImageSizeValidator

class User(AbstractBaseUser, PermissionsMixin):
    login = models.CharField(
        _('login'),
        max_length=255,
        unique=True,
        help_text="At most 255 characters.",
        validators=[MinLengthValidator(4)]
    )
    email = models.EmailField(_('email'), unique=True)
    phone = models.DecimalField(
        _('phone number'),
        max_digits=15,
        decimal_places=0,
        unique=True,
        help_text="Phone number in international format without '+','(',')','-'."
    )
    email_confirmed = models.BooleanField(_('email confirmed'), default=False)
    date_of_creation = models.DateTimeField(
        _('date of creation'),
        auto_now_add = True,
        auto_now = False
    )
    date_of_update = models.DateTimeField(
        _('date of update'),
        auto_now_add = False,
        auto_now = True
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'login'
    REQUIRED_FIELDS = ('email', 'phone')

    def __str__(self):
        return self.login + ": " + self.email

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)


class UserPersonalData(models.Model):
    first_name = models.CharField(
        _('first name'),
        max_length=255,
        null=True,
        help_text="At most 255 characters."
    )
    last_name = models.CharField(
        _('last name'),
        max_length=255,
        null=True,
        blank=True,
        help_text="At most 255 characters."
    )
    avatar = models.ImageField(
        _('avatar'),
        upload_to=get_userpic_path,
        validators=[
            FileExtensionValidator(allowed_extensions=('jpg','jpeg')),
            MinImageSizeValidator(250, 250)
        ],
        null=True,
        blank=True
    )
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    about_myself = models.TextField(_('about myself'), null=True, blank=True)
    technologies = models.ManyToManyField(
        'projectApp.Technology',
        related_name='users',
        verbose_name=_('programming languages/technologies'),
        blank=True
    )

    auth_data = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='personal_data',
        on_delete=models.CASCADE,
        verbose_name=_('user\'s authorizing data')
    )

    class Meta:
        verbose_name = _("personal data of a user")
        verbose_name_plural = _("personal data of users")

    def __str__(self):
        names = (self.first_name, self.last_name, self.auth_data.login)
        return "%s %s (%s)" % names

    # Handling user's profile picture:
    avatar_size = (460, 460) # size in pixels
    avatar_thumbnail_size = (150, 150) # size in pixels

    def _get_avatar_dir(self):
        """ Returns path to directory for user's avatar. """
        user_dir = "user_%s" % self.auth_data.id
        return os.path.join(settings.MEDIA_ROOT, 'userApp', 'avatar', user_dir)

    def _make_avatar_from_field(self):
        if not self.avatar: return None

        # Verify if there user picture's directory exists:
        image_dir = self._get_avatar_dir()
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        # Resizing given user's picture:
        correct_image = Image.open(self.avatar.file).resize(self.avatar_size)
        image_bytestream = io.BytesIO()
        correct_image.save(image_bytestream, 'JPEG')
        self.avatar.file = image_bytestream

        # Creating thumbnail:
        correct_image.thumbnail(self.avatar_thumbnail_size)
        thumbnail_name = get_thumbnail_name(self.avatar.name)
        thumbnail_path = os.path.join(image_dir, thumbnail_name)
        correct_image.save(thumbnail_path, 'JPEG')

    def _update_avatar(self):
        # Check avatar, if it is updated or removed, delete old image:
        try:
            old_avatar = UserPersonalData.objects.get(id=self.id).avatar
            # In case of changes of avatar:
            if self.avatar != old_avatar:
                # If old avatar is present, it should be removed:
                if old_avatar:
                    # Remove avatar thumbnail:
                    thumbnail_path = os.path.join(
                        settings.MEDIA_ROOT,
                        get_thumbnail_name(old_avatar.name)
                    )
                    os.remove(thumbnail_path)
                    # Remove avatar:
                    old_avatar.delete(save=False)

                # If there is a new avatar, it should be stored:
                self._make_avatar_from_field()

        except (UserPersonalData.DoesNotExist, FileNotFoundError):
            self._make_avatar_from_field()

    def save(self, *args, **kwargs):
        self._update_avatar()
        super().save(*args, **kwargs)


class UserProgress(models.Model):
    level = models.PositiveSmallIntegerField(
        _('level'),
        default=0
    )
    amount_tasks = models.PositiveSmallIntegerField(
        _('amount tasks'),
        default=0
    )
    reputation_point = models.PositiveIntegerField(
        _('reputation point'),
        default=0
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='progress',
        on_delete=models.CASCADE,
        verbose_name=_('user')
    )

    class Meta:
        verbose_name = _("user's progress")
        verbose_name_plural = _("progress of users")

    def __str__(self):
        line = "%s: level = %d, rating = %d"
        return line % (self.user.login, self.level, self.reputation_point)


class AccountActivationCode(models.Model):
    code = models.TextField(_('account activation code'), blank=True)
    date_of_creation = models.DateTimeField(auto_now_add=True, auto_now=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='activation_code',
        on_delete=models.CASCADE,
        verbose_name=_('user')
    )

    email_message_template = {
        'subject': _("MLP Account Activation"),
        'body': _(
            "Hi, %(username)s!\n" +
            "To activate your account, follow the next link:\n" +
            "%(link)s"
        )
    }
    link_template = (
        "%(protocol)s://%(hostname)s:%(port)d"
        "/api/v1/account-activation/%(code)s/"
    )
    expiration_term = timedelta(hours=24)

    class Meta:
        verbose_name = _("account activation code")
        verbose_name_plural = _("account activation codes")

    @classmethod
    def get_actuals(cls):
        """
        Returns filtered queryset of model items,
        which was created not later then expiration date.
        """
        time_floor = timezone.now() - cls.expiration_term
        return cls.objects.filter(date_of_creation__gte=time_floor)

    def __str__(self):
        return self.code

    def _generate_link(self):
        """ Returns reliable account activation link. """

        # Like a temporary solution, we can user a pre-defined
        # dictionary in settings_dev.py to configure an absolute url base
        # depending on development server's parameters
        return self.link_template % {
            'protocol': settings.MLP_WEBSITE['protocol'],
            'hostname': settings.MLP_WEBSITE['hostname'],
            'port': settings.MLP_WEBSITE['port'],
            'code': self.code
        }

    def notificate_user(self):
        msg_body = {'username': self.user.login, 'link': self._generate_link()}
        self.user.email_user(
            self.email_message_template['subject'],
            self.email_message_template['body'] % msg_body,
        )

    def save(self, *args, **kwargs):
        self.code = generate_random_string(30, 40)
        self.notificate_user()
        super().save(*args, **kwargs)
