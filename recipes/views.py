from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from .forms import RecipeForm
from .models import Recipe, Tag
from .logic import (get_paginated_view,
                    get_request_tags,
                    save_recipe,
                    edit_recipe)

User = get_user_model()


def index(request):
    tags = get_request_tags(request)
    recipes = Recipe.objects.filter(tags__title__in=tags).select_related(
        'author').prefetch_related('tags').distinct()

    page, paginator = get_paginated_view(request, recipes)
    context = {
        'page': page,
        'paginator': paginator,
        'tags': tags,
        'all_tags': Tag.objects.all(),
    }
    return render(request, 'index.html', context)


@login_required
def new_recipe(request):
    form = RecipeForm(request.POST or None, files=request.FILES or None)

    if form.is_valid():
        recipe = save_recipe(request, form)

        return redirect(
            'recipe_view_slug', recipe_id=recipe.id, slug=recipe.slug
        )

    context = {'form': form}
    return render(request, 'formRecipe.html', context)


def profile(request, username):
    tags = get_request_tags(request)
    author = get_object_or_404(User, username=username)
    author_recipes = author.recipes.filter(
        tags__title__in=tags).prefetch_related('tags').distinct()

    page, paginator = get_paginated_view(request, author_recipes)
    context = {
        'author': author,
        'page': page,
        'paginator': paginator,
        'tags': tags,
        'all_tags': Tag.objects.all(),
    }
    return render(request, 'authorRecipe.html', context)


def recipe_view(request, recipe_id):
    recipe = get_object_or_404(Recipe.objects.all(), id=recipe_id)
    return redirect('recipe_view_slug', recipe_id=recipe.id, slug=recipe.slug)


@login_required
def recipe_edit(request, recipe_id, slug):
    recipe = get_object_or_404(Recipe, id=recipe_id)

    if not request.user.is_superuser:
        if request.user != recipe.author:
            return redirect(
                'recipe_view_slug', recipe_id=recipe.id, slug=recipe.slug
            )

    form = RecipeForm(
        request.POST or None,
        files=request.FILES or None,
        instance=recipe
    )

    if form.is_valid():
        edit_recipe(request, form, instance=recipe)
        return redirect(
            'recipe_view_slug', recipe_id=recipe.id, slug=recipe.slug
        )

    context = {'form': form, 'recipes': recipe}
    return render(request, 'formRecipe.html', context)


@login_required
def recipe_delete(request, recipe_id, slug):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if request.user.is_superuser or request.user == recipe.author:
        recipe.delete()
    return redirect('index')


def recipe_view_slug(request, recipe_id, slug):
    recipe = get_object_or_404(
        Recipe.objects.select_related('author'),
        id=recipe_id,
        slug=slug
    )
    context = {'recipe': recipe}
    return render(request, 'singlePage.html', context)


@login_required
def subscriptions(request):
    authors = User.objects.filter(
        following__user=request.user).prefetch_related('recipes').annotate(
        recipe_count=Count('recipes')).order_by('username')

    page, paginator = get_paginated_view(request, authors)
    context = {'page': page, 'paginator': paginator}
    return render(request, 'subscriptions.html', context)


@login_required
def favorites(request):
    tags = get_request_tags(request)
    recipe = Recipe.objects.filter(
        favored_by__user=request.user, tags__title__in=tags
    ).select_related('author').prefetch_related('tags').distinct()

    page, paginator = get_paginated_view(request, recipe)
    context = {
        'page': page,
        'paginator': paginator,
        'tags': tags,
        'all_tags': Tag.objects.all(),
    }
    return render(request, 'favorite.html', context)


@login_required
def purchases(request):
    recipes = request.user.purchases.all()
    return render(request, 'shopList.html', {'recipes': recipes})


@login_required
def purchases_download(request):
    title = 'recipe__ingredients__title'
    dimension = 'recipe__ingredients__dimension'
    quantity = 'recipe__ingredients_amounts__quantity'

    ingredients = request.user.purchases.select_related('recipes').order_by(
        title).values(title, dimension).annotate(amount=Sum(quantity)).all()

    if not ingredients:
        return render(request, 'misc/400.html', status=400)

    text = 'Список покупок:\n\n'
    for number, ingredient in enumerate(ingredients, start=1):
        amount = ingredient['amount']
        text += (
            f'{number}) '
            f'{ingredient[title]} - '
            f'{amount} '
            f'{ingredient[dimension]}\n'
        )

    response = HttpResponse(text, content_type='text/plain')
    filename = 'shopping_list.txt'
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response
