# Sample data

From the challenge diagrams. Upload these in the app to exercise each pattern.

## `sample.csv`

| Row | A | B | C | Purpose |
|-----|---|---|---|---------|
| 1 | Dog | China | Line | **Negative:** `-200` in 202402. Also useful for **pipeline demo** with row 4. |
| 2 | Dog | Shine | Lime | **Negative:** `-100` in 202403 (matches UI mockup row). |
| 3 | Cat | USA | Retail | **Refund:** `200` + `-200` in 202402–202403 (sum = 0). |
| 4 | Bird | UK | Online | **Refund:** `200` + `-200` in 202401–202402. If you accept negatives on a similar row first, refund proposals can change — compare with row 1 after cleaning negatives. |
| 5 | (empty) | | | **Double booking:** `100` and `0` in 202401–202402 → fix splits to `50` / `50`. |