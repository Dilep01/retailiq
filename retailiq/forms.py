from django import forms


class ImportForm(forms.Form):
    name = forms.CharField(max_length=160, initial="My retail sales")
    currency = forms.ChoiceField(choices=[(v, v) for v in ["INR", "GBP", "USD", "EUR"]])
    file = forms.FileField()

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > 10 * 1024 * 1024 or not file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Choose a CSV file smaller than 10 MB.")
        return file


class PlanForm(forms.Form):
    budget = forms.DecimalField(min_value=0, max_value=100000000, initial=25000, decimal_places=2)
    review = forms.IntegerField(min_value=1, max_value=21, initial=7, label="Review every (days)")
    service = forms.ChoiceField(
        choices=[(".90", "90% normal target"), (".95", "95% normal target"), (".99", "99% normal target")],
        initial=".95",
    )
    solver = forms.ChoiceField(choices=[("heuristic", "Priority allocation"), ("milp", "Integer optimization")])


class SimulationForm(forms.Form):
    days = forms.IntegerField(min_value=14, max_value=84, initial=56, label="Scenario length (days)")
    budget = forms.DecimalField(
        min_value=0, max_value=100000000, initial=750000, label="Budget per weekly review", decimal_places=2
    )
    delay = forms.IntegerField(min_value=0, max_value=14, initial=0, label="Additional delivery delay (days)")


class StockForm(forms.Form):
    on_hand = forms.IntegerField(min_value=0, max_value=10000000)
    on_order = forms.IntegerField(min_value=0, max_value=10000000, initial=0)
    allocated = forms.IntegerField(min_value=0, max_value=10000000, initial=0)
    as_of = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    unit_cost = forms.DecimalField(min_value=0.01, max_value=1000000, decimal_places=2)
    lead_time = forms.IntegerField(min_value=1, max_value=21)
    pack_size = forms.IntegerField(min_value=1, max_value=10000)
    moq = forms.IntegerField(min_value=1, max_value=10000)
    assumptions = forms.BooleanField(required=False, initial=True, label="These are scenario assumptions")
