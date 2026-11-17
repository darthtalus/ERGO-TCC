from django.core import serializers
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from dimensions.models import Dimension
from user_dimensions.models import UserDimension
from user_aspects.models import UserAspects
from tasks.models import Task



def root(request):
    if (request.user.is_authenticated):
        return redirect('tasks_index')
    else:
        return redirect('login')





def index(request):
    
    dimensions = Dimension.objects.all()
    context = {'dimensions': list(dimensions)}
    return render(request, 'pages/index.html', context)


def main(request):
    tasks = Task.objects.filter(user=request.user) if request.user.is_authenticated else Task.objects.none()
    context = {'mytasks': tasks}
    return render(request, 'pages/main.html', context)


def new_task(request):
    return render(request, 'pages/new.html')


def privacy_policy(request):
    return render(request, 'pages/privacy_policy.html')


def changeparam(request, id, val):
    UserAspects.objects.filter(pk=id).update(parametrized=val)
    return redirect(reverse('params') + "?" + request.GET.urlencode())


def changewatch(request, id, val):
    newval = False
    if val == 0:
        newval = False
    else:
        newval = True

    UserAspects.objects.filter(pk=id).update(watched=newval)
    return redirect(reverse('params') + "?" + request.GET.urlencode())


def index_ajax(request):
    if request.method == 'POST':
        user_id = request.POST['uduser_id']
        dimension_id = request.POST['uddimension_id']
        aspect_name = request.POST['aspect_name']
        aspect_value = request.POST['aspect_value']

        try:
            user_dimension = UserDimension.objects.get(
                user_id=user_id, dimension_id=dimension_id)
        except UserDimension.DoesNotExist:
            user_dimension = UserDimension.objects.create(
                user_id=user_id, dimension_id=dimension_id)

        user_aspects = UserAspects.objects.create(
            user_dimension=user_dimension, nome=aspect_name, valor=aspect_value)
        return JsonResponse({'data': user_aspects.to_dict()})
    elif request.method == 'GET':
        user_id = request.GET['user_id']
        dimension_id = request.GET['dimension_id']
        try:
            user_dimension = UserDimension.objects.get(
                user_id=user_id, dimension_id=dimension_id)
        except UserDimension.DoesNotExist:
            return JsonResponse({'data': [] })
        user_aspects = UserAspects.objects.filter(user_dimension_id=user_dimension.id)
        user_aspects_serialized = serializers.serialize("json", user_aspects)
        return JsonResponse({'data': user_aspects_serialized })


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)
