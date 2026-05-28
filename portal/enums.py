"""Domain enumerations shared across models, forms and the affordability engine."""

from django.db import models


class ProjectPurpose(models.TextChoices):
    BUY = "buy", "Buy a property"
    BUILD = "build", "Build a new property"
    BUY_OUT = "buy_out", "Buy out"
    RENOVATE = "renovate", "Renovate my property"
    REFINANCE = "refinance", "Refinance my mortgage"


class BorrowerCount(models.IntegerChoices):
    ALONE = 1, "Alone"
    WITH_SOMEONE = 2, "With someone"


class PropertyType(models.TextChoices):
    HOUSE = "house", "House"
    APARTMENT = "apartment", "Apartment"
    LAND = "land", "Building land"


class Region(models.TextChoices):
    FLANDERS = "flanders", "Flanders"
    WALLONIA = "wallonia", "Wallonia"
    BRUSSELS = "brussels", "Brussels"


class PropertyUsage(models.TextChoices):
    OWN_HOME = "own_home", "Own and only home"
    SECOND_HOME = "second_home", "Second home"
    INVESTMENT = "investment", "Investment property"


class IncomeType(models.TextChoices):
    SALARY = "salary", "Salary (employee)"
    SELF_EMPLOYED = "self_employed", "Self-employed / business owner"
    RENTAL = "rental", "Rental income"
    REPLACEMENT = "replacement", "Replacement income"
    OTHER = "other", "Other"


class ExpenseType(models.TextChoices):
    EXISTING_LOAN = "existing_loan", "Existing loan"
    RENT = "rent", "Rent"
    ALIMONY = "alimony", "Alimony"
    OTHER = "other", "Other"


class EmploymentStatus(models.TextChoices):
    EMPLOYEE = "employee", "Employee"
    SELF_EMPLOYED = "self_employed", "Self-employed"
    CIVIL_SERVANT = "civil_servant", "Civil servant"
    RETIRED = "retired", "Retired"
    OTHER = "other", "Other"


class DocumentKind(models.TextChoices):
    ID_CARD = "id_card", "Identity card"
    PAYSLIP = "payslip", "Payslip"
    EPC_CERTIFICATE = "epc_certificate", "EPC certificate"
    SALES_AGREEMENT = "sales_agreement", "Sales agreement"
    BANK_STATEMENT = "bank_statement", "Bank statement"
    OTHER = "other", "Other supporting document"
