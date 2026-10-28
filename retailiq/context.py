from .models import Dataset


def navigation(request):
    datasets = Dataset.objects.order_by("id")
    selected = request.GET.get("dataset") or request.session.get("dataset")
    try:
        dataset = datasets.filter(pk=int(selected)).first() if selected else datasets.first()
    except (TypeError, ValueError):
        dataset = datasets.first()
    if dataset:
        request.session["dataset"] = dataset.id
    return {
        "datasets": datasets,
        "dataset": dataset,
        "page_key": request.resolver_match.url_name if request.resolver_match else "",
        "currency": dataset.currency if dataset else "INR",
    }
