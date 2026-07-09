from src.excel.loaders import DataLoader
from src.excel.workbook import create_workbook
from src.excel.writers import ExcelWriter

print("Loading data...")

loader = DataLoader().load()

print(loader.summary())

wb = create_workbook()

writer = ExcelWriter(
    wb,
    loader
)

writer.build()

wb.save("DTIA_Compliance_Database.xlsx")

print()
print("Done.")
print("Workbook saved as DTIA_Compliance_Database.xlsx")