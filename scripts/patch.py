import pandas as pd

df = pd.read_csv('overrides/todo_517.csv', encoding='utf-8-sig', keep_default_na=False)

for idx in range(216):
    if df.at[idx, '平日雙人房價'] == "":
        df.at[idx, '平日雙人房價'] = "查無"

df.to_csv('overrides/todo_517.csv', index=False, encoding='utf-8-sig')
print("Patched first 216 rows to '查無'")
