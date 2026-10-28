from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from retailiq import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", views.overview, name="overview"),
    path("data/", views.data_page, name="data"),
    path("data/commit/<int:pk>/", views.commit_import, name="commit_import"),
    path("data/template/", views.csv_template, name="csv_template"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/", views.product_detail, name="product"),
    path("forecasts/", views.forecasts, name="forecasts"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/<int:pk>/edit/", views.stock_edit, name="stock_edit"),
    path("scenarios/", views.scenarios, name="scenarios"),
    path("runs/", views.runs, name="runs"),
    path("export/<str:kind>/<int:pk>/", views.export_csv, name="export"),
    path("api/health/", views.health, name="health"),
    path("api/jobs/<int:pk>/", views.job_status, name="job_status"),
]
