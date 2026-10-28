from django.conf import settings
from django.db import models


class Dataset(models.Model):
    name = models.CharField(max_length=160)
    source_kind = models.CharField(max_length=20, default="synthetic")
    currency = models.CharField(max_length=3, default="INR")
    checksum = models.CharField(max_length=64, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    sku = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=60, default="General")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    lead_time = models.PositiveIntegerField(default=5)
    pack_size = models.PositiveIntegerField(default=1)
    moq = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["dataset", "sku"], name="dataset_sku"),
            models.CheckConstraint(condition=models.Q(pack_size__gte=1), name="positive_pack"),
            models.CheckConstraint(condition=models.Q(lead_time__gte=1), name="positive_lead"),
        ]

    def __str__(self):
        return self.name


class Location(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["dataset", "name"], name="dataset_location")]


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    date = models.DateField()
    units = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    observed = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "location", "date"], name="daily_sale")]
        indexes = [models.Index(fields=["product", "location", "date"])]


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    as_of = models.DateField()
    on_hand = models.PositiveIntegerField(default=0)
    on_order = models.PositiveIntegerField(default=0)
    allocated = models.PositiveIntegerField(default=0)
    assumptions = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "location"], name="stock_location")]


class ImportBatch(models.Model):
    name = models.CharField(max_length=160)
    checksum = models.CharField(max_length=64)
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    currency = models.CharField(max_length=3, default="INR")
    dataset = models.ForeignKey(Dataset, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    kind = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="queued")
    params = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)


class ForecastRun(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    origin = models.DateField()
    horizon = models.PositiveIntegerField(default=28)
    model_name = models.CharField(max_length=60)
    metadata = models.JSONField(default=dict)
    evaluation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ForecastPoint(models.Model):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    date = models.DateField()
    prediction = models.FloatField()
    lower = models.FloatField(null=True)
    upper = models.FloatField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "product", "location", "date"], name="forecast_target")]


class Plan(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    forecast = models.ForeignKey(ForecastRun, on_delete=models.PROTECT)
    params = models.JSONField(default=dict)
    lines = models.JSONField(default=list)
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Simulation(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    params = models.JSONField(default=dict)
    results = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
