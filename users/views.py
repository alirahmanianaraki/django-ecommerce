from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .token import account_activation_token
from .models import Address
from .forms import (CreateUserForm, 
                    LoginForm, 
                    ProfileForm,
                    AddressForm
                    )

# Create your views here.
def register_user(request):
    form = CreateUserForm()
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            current_domain = get_current_site(request)
            # Email Verfication Logic
            subject = 'Verify your email',
            message = render_to_string('users/email_verification.html',
                                       {
                                           'domain': current_domain,
                                           'uid64': urlsafe_base64_encode(force_bytes(user.pk)),
                                           'token': account_activation_token.make_token(user)
                                       })
            user.email_user(subject=subject, message=message)
            return redirect('users:email_verification_sent')
        
    return render(request, 'users/register.html',
                  {
                      'form': form
                  })

def email_verification(request, uidb64, token):
    user_id = force_str(urlsafe_base64_decode(uidb64))
    user = get_object_or_404(User, pk=user_id)
    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return redirect('users:email_verification_success')
    else:
        return redirect('users:email_verification_failed')

def email_verification_sent(request,):
    return render(request, 'users/email_verification_sent.html')

def email_verification_success(request):
    return render(request, 'users/email_verification_success.html')

def email_verification_failed(request):
    return render(request, 'users/email_verification_failed.html')

def user_login(request):
    if request.user.is_authenticated:
        messages.error(request, 'You are already logged in')
        return redirect('myapp:index')

    if request.method == 'POST':
        login_form = LoginForm(request, data=request.POST)
        if login_form.is_valid():
            cart_data = request.session.get('cart', {})
            username = login_form.cleaned_data.get('username')
            password = login_form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                request.session['cart'] = cart_data
                request.session.modified = True
                messages.success(request, 'You have successfully logged in')
                return redirect('myapp:index')
    
    login_form = LoginForm()
    return render(request, 'users/login.html',
                  {
                      'login_form': login_form
                  })

def user_logout(request):
    cart_data = request.session.get('cart', {})
    if not request.user.is_authenticated:
        messages.error(request, 'You are not logged in')
        return redirect('myapp:index')
    else:
        logout(request)
        request.session['cart'] = cart_data
        request.session.modified = True
        messages.success(request, 'You have successfully logged out')
        return redirect('myapp:index')

@login_required(login_url='users:login')
def profile(request):
    user = request.user
    user_address = user.user_address.first()
    return render(request, 'users/profile.html',
                  {
                      'user': user,
                      'user_address': user_address
                  })

@login_required(login_url='users:login')
def modify_user_info(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        current_domain = get_current_site(request)
        current_email = request.user.email
        if form.is_valid():
            user = form.save(commit=False)
            new_email = form.cleaned_data.get('email')
            if current_email.lower() == new_email.lower():
                user.save()
                messages.success(request, 'Modified user info successfully')
                return redirect('users:profile')
            else:
                user.is_active = False
                user.save()
                messages.warning(request,'Verify the newely entered email')
                subject = 'Verify your new email'
                email_message = render_to_string('users/email_verification.html',
                                           {
                                               'domain': current_domain,
                                               'uid64': urlsafe_base64_encode(force_bytes(user.pk)),
                                               'token': account_activation_token.make_token(user)
                                           })
                user.email_user(subject=subject, message=email_message)
                return redirect('users:email_verification_sent')

    else:       
        form = ProfileForm(instance=request.user)
    return render(request, 'users/modify_user_info.html',
                  {
                      'form': form
                  })

@login_required(login_url='users:login')
def add_address(request):
    current_user = request.user
    user_address = Address.objects.filter(user=current_user).first()
    form = AddressForm(instance=user_address)
    if request.method == 'POST':
        form = AddressForm(instance=user_address, data=request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = current_user
            address.save()
            messages.success(request, 'Saved the address')
            return redirect('users:profile')
    return render(request, 'users/add_address.html',
                  {
                      'form': form,
                  })