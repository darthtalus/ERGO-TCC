from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages, auth
from django.utils.translation import gettext as _
import random
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from .models import CustomUser
from .forms import UserEditForm, UserProfileForm
from tasks.models import Task, TaskInvitation, TaskUser
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import os

@login_required
def user_edit(request, user_id):
    if request.user.role not in ['SUPERADMIN', 'ADMIN']:
        messages.error(request, _('Access denied.'))
        return redirect('tasks_index')
    
    user_to_edit = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user_to_edit, is_superadmin=(request.user.role == 'SUPERADMIN'))
        if form.is_valid():
            user = form.save(commit=False)
            if user.role == 'SUPERADMIN':
                user.is_staff = True
                user.is_superuser = True
            else:
                user.is_staff = False
                user.is_superuser = False
            user.save()

            new_password = form.cleaned_data.get('new_password')
            if new_password and request.user.role == 'SUPERADMIN':
                user.set_password(new_password)
                user.save()
            messages.success(request, f'Usuário {user_to_edit.username} atualizado com sucesso.')
            return redirect('user_list')

    else:
        form = UserEditForm(instance=user_to_edit, is_superadmin=(request.user.role == 'SUPERADMIN'))
    
    participations_qs = TaskUser.objects.filter(
        user=user_to_edit
    ).select_related('task', 'task__user')

    executor_count = participations_qs.filter(type=Task.UserType.EXECUTOR).count()
    stakeholder_count = participations_qs.filter(type=Task.UserType.STAKEHOLDER).count()

    sort = request.GET.get('sort', 'task__created_at')
    order = request.GET.get('order', 'desc')

    valid_sorts = {
        'task__id': 'task__id',
        'task__name': 'task__name',
        'type': 'type',
        'status': 'status',
        'task__created_at': 'task__created_at',
    }
    sort_field = valid_sorts.get(sort, 'task__created_at')
    if order == 'desc':
        sort_field = f'-{sort_field}'

    task_participations = participations_qs.order_by(sort_field)

    return render(request, 'accounts/user_edit.html', {
        'form': form,
        'user_to_edit': user_to_edit,
        'task_participations': task_participations,
        'executor_count': executor_count,
        'stakeholder_count': stakeholder_count,
        'current_sort': sort,
        'current_order': order,
    })

@login_required
def user_list(request):
    if request.user.role not in ['SUPERADMIN', 'ADMIN']:
        messages.error(request, _('Access denied.'))
        return redirect('tasks_index')

    sort = request.GET.get('sort', 'username')
    order = request.GET.get('order', 'asc')

    valid_sorts = {
        'username': 'username',
        'full_name': ('first_name', 'last_name'),
        'email': 'email',
        'role': 'role',
        'date_joined': 'date_joined',
        'last_login': 'last_login',
        'is_active': 'is_active',
    }

    sort_field = valid_sorts.get(sort, 'username')
    if order == 'desc':
        if isinstance(sort_field, tuple):
            sort_field = tuple(f'-{f}' for f in sort_field)
        else:
            sort_field = f'-{sort_field}'

    users = CustomUser.objects.all().order_by(*sort_field) if isinstance(sort_field, tuple) else CustomUser.objects.all().order_by(sort_field)

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'roles': CustomUser.ROLE_CHOICES,
        'current_sort': sort,
        'current_order': order,
    })


def register(request):
    if request.method == 'POST':
        # Anti-spam: Honeypot check
        if request.POST.get('website_url', ''):
            messages.error(request, _('Bot detected.'))
            return redirect('register')
            
        # Anti-spam: CAPTCHA check
        if not request.user.is_authenticated:
            user_captcha = request.POST.get('captcha', '').strip().lower()
            correct_captcha = request.session.get('captcha_code', '').lower()
            
            if not correct_captcha or user_captcha != correct_captcha:
                messages.error(request, _('Incorrect CAPTCHA code! Please try again.'))
                return redirect('register')

            # Clear captcha after validation
            request.session.pop('captcha_code', None)

        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        country = request.POST['country']
        birthdate = request.POST.get('birthdate')
        company = request.POST['company']
        email = request.POST['email']
        password = request.POST['password']
        password2 = request.POST['password2']


        if password != password2:
            messages.error(request, _('Passwords do not match'))
            return redirect('register')

        # Password complexity validation
        import re
        if len(password) < 6:
            messages.error(request, _('Password must be at least 6 characters long.'))
            return redirect('register')
        
        if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
            messages.error(request, _('Password must contain at least one letter and one number.'))
            return redirect('register')

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, _('Username is being used'))
            return redirect('register')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, _('Email is being used'))
            return redirect('register')

        user = CustomUser.objects.create_user(
            username=username, password=password,
            email=email, first_name=first_name,
            last_name=last_name, birthdate=birthdate,
            company=company, country=country)
        
        # Check for invitation
        invitation_id = request.POST.get('invitation_id')
        if invitation_id:
            try:
                invitation = TaskInvitation.objects.get(id=invitation_id, email__iexact=email, accepted=False)
                if not invitation.is_expired:
                    TaskUser.objects.create(
                        task=invitation.task,
                        user=user,
                        type=invitation.type
                    )
                    invitation.accepted = True
                    invitation.save()
                    messages.success(request, _('You have been added to the task "%(name)s"!') % {'name': invitation.task.name})
                else:
                    messages.warning(request, _("The invitation linked to this registration has expired."))
            except TaskInvitation.DoesNotExist:
                pass

        # Enviar email de boas-vindas
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        subject = _('Welcome to Ergo!')
        html_message = render_to_string('accounts/emails/welcome_email.html', {'user': user, 'request': request})
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to = email

        try:
            send_mail(subject, plain_message, from_email, [to], html_message=html_message)
        except Exception as e:
            # Em caso de erro no envio do email, apenas registramos no log mas não impedimos o cadastro
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao enviar email de boas-vindas: {e}")

        messages.success(request, _('User created successfully'))
        
        # Se for um administrador logado cadastrando outro usuário, redireciona para a lista
        if request.user.is_authenticated and request.user.role in ['SUPERADMIN', 'ADMIN']:
            return redirect('user_list')
            
        return redirect('login')

    else:
        return render(request, 'accounts/register.html')


def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(request=request, username=username, password=password)

        if user is not None:
            auth.login(request, user)
            messages.success(request, _('You are now logged in'))
            
            # Check for birthday
            from django.utils import timezone
            today = timezone.localdate()
            if user.birthdate and user.birthdate.day == today.day and user.birthdate.month == today.month:
                messages.info(request, _('Happy Birthday, %(name)s! 🎂') % {'name': user.first_name or user.username})
                
            next_url = request.POST.get('next') or request.GET.get('next') or 'tasks_index'
            # Security: validate redirect URL to prevent Open Redirect attacks
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = 'tasks_index'
            return redirect(next_url)
        else:
            messages.error(request, _('Invalid credentials'))
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(f"{reverse('login')}?next={next_url}")
            return redirect('login')
    else:
        return render(request, 'accounts/login.html')


def logout(request):
    if request.method != 'POST':
        return redirect('login')
    auth.logout(request)
    messages.success(request, _('You are now logged out'))
    return redirect('login')


def generate_captcha(request):
    width, height = 120, 50
    chars = 3
    possible_letters = '23456789bcdfghjkmnpqrstvwxyz'
    
    # 1. Gera o código e salva na sessão
    code = "".join(random.choice(possible_letters) for _ in range(chars))
    request.session['captcha_code'] = code # Usamos isso para validar no login
    
    # 2. Cria a imagem (RGB) com a cor de fundo (Azul claro: 176, 196, 222)
    image = Image.new('RGB', (width, height), (176, 196, 222))
    draw = ImageDraw.Draw(image)
    
    # 3. Adiciona o ruído (linhas) para aumentar a segurança
    text_color = (20, 40, 100) # Azul escuro (0x142864)
    for _ in range(15):
        draw.line([(random.randint(0, width), random.randint(0, height)), 
                   (random.randint(0, width), random.randint(0, height))], 
                  fill=text_color, width=1)
    
    # 4. Carrega a fonte e desenha o texto
    basedir = settings.BASE_DIR
    windows_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    font_paths = [
        os.path.join(windows_fonts, "arial.ttf"),       # Windows
        os.path.join(windows_fonts, "segoeui.ttf"),     # Windows fallback
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", # Ubuntu/Debian
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", # Oracle/RedHat (Linux remoto)
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"
    ]
    
    font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 40)
                break
            except:
                continue
                
    if font is None:
        font = ImageFont.load_default()
        
    # Desenha o texto (centralizado aproximado)
    draw.text((25, 2), code, fill=text_color, font=font)
    
    # 5. Envia a imagem para o navegador sem salvar arquivo no disco (Buffer)
    img_io = io.BytesIO()
    image.save(img_io, 'JPEG', quality=90)
    img_io.seek(0)
    return HttpResponse(img_io.getvalue(), content_type='image/jpeg')


from django.contrib.auth.views import PasswordResetView
import logging

logger = logging.getLogger(__name__)

class SafePasswordResetView(PasswordResetView):
    def post(self, request, *args, **kwargs):
        # Anti-spam: Honeypot check
        if request.POST.get('website_url', ''):
            messages.error(request, _('Bot detected.'))
            return redirect('password_reset')
            
        # Anti-spam: CAPTCHA check
        user_captcha = request.POST.get('captcha', '').strip().lower()
        correct_captcha = request.session.get('captcha_code', '').lower()
        
        if not correct_captcha or user_captcha != correct_captcha:
            messages.error(request, _('Incorrect CAPTCHA code! Please try again.'))
            return redirect('password_reset')

        # Clear captcha after validation
        request.session.pop('captcha_code', None)
            
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error processing password reset: {e}")
            messages.error(self.request, _("There was a technical problem sending the reset email. Please try again later or contact support."))
            return self.get(request, *args, **kwargs)


@login_required
def admin_send_password_reset(request, user_id):
    if request.user.role not in ['SUPERADMIN', 'ADMIN']:
        messages.error(request, _('Action not allowed.'))
        return redirect('tasks_index')
    
    user_to_reset = get_object_or_404(CustomUser, id=user_id)
    
    if not user_to_reset.email:
        messages.error(request, _('The user does not have an email address registered.'))
        return redirect('user_edit', user_id=user_id)
    
    from django.contrib.auth.forms import PasswordResetForm
    form = PasswordResetForm({'email': user_to_reset.email})
    
    if form.is_valid():
        try:
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name='accounts/emails/password_reset_email.html',
                subject_template_name='accounts/emails/password_reset_subject.txt',
                from_email=settings.DEFAULT_FROM_EMAIL,
            )
            messages.success(request, _('Reset email successfully sent to %(email)s.') % {'email': user_to_reset.email})
        except Exception as e:
            logger.error(f"Error sending reset by admin: {e}")
            messages.error(request, _('Error sending email. Please check SMTP settings.'))
            
    return redirect('user_edit', user_id=user_id)


@login_required
def user_delete(request, user_id):
    if request.user.role != 'SUPERADMIN':
        messages.error(request, _('Only SuperAdmins can delete users.'))
        return redirect('user_list')
    
    user_to_delete = get_object_or_404(CustomUser, id=user_id)

    if user_to_delete.id == 1:
        messages.error(request, _('The main administrator (ID=1) cannot be deleted.'))
        return redirect('user_list')

    if user_to_delete == request.user:
        messages.error(request, _('You cannot delete your own account.'))
        return redirect('user_list')

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password')
        
        # Verify SuperAdmin's password
        if not request.user.check_password(admin_password):
            messages.error(request, _('Invalid password. Deletion cancelled.'))
            return render(request, 'accounts/user_delete_confirm.html', {'user_to_delete': user_to_delete})

        username = user_to_delete.username
        
        try:
            from django.db import transaction
            from tasks.models import Task, TaskUser, TaskRate
            from user_aspects.models import UserAspects, Effectiveness
            from user_dimensions.models import UserDimension
            
            with transaction.atomic():
                # 1. Reassign tasks owned by the user to Admin ID=1 instead of deleting them
                Task.objects.filter(user=user_to_delete).update(user_id=1)
                
                # 2. Delete profile related data that doesn't cascade
                UserAspects.objects.filter(user=user_to_delete).delete()
                UserDimension.objects.filter(user_id=user_to_delete.id).delete()
                
                # 3. Effectiveness records (should cascade but being safe)
                Effectiveness.objects.filter(user=user_to_delete).delete()
                
                # 4. The user itself (will cascade to TaskUser, TaskRate, etc.)
                user_to_delete.delete()
                
            messages.success(request, _('User %(username)s has been deleted. Tasks were reassigned to the administrator.') % {'username': username})
            return redirect('user_list')
        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            messages.error(request, _('An error occurred while deleting the user.'))
            return redirect('user_list')
            
    return render(request, 'accounts/user_delete_confirm.html', {'user_to_delete': user_to_delete})

@login_required
def profile(request):
    user = request.user
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Your profile has been updated successfully.'))
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user)
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'user': user
    })
