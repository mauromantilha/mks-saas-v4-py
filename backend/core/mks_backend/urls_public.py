from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
    # Aqui entrarão as rotas da Landing Page e Login Global
]
