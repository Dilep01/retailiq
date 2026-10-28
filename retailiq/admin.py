from django.contrib import admin
from .models import Dataset, Product, Location, Stock, Job, ForecastRun, Plan, Simulation, AuditEvent

for model in [Dataset, Product, Location, Stock, Job, ForecastRun, Plan, Simulation, AuditEvent]:
    admin.site.register(model)
