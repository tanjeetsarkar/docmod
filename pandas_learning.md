# Complete Pandas + NumPy Learning Roadmap

## 1. Setup Your Environment

### Install Python

Download Python 3.11+:

https://www.python.org/downloads/

Verify installation:

```bash
python --version
```

---

## Install VS Code (Not Required)

Download:

https://code.visualstudio.com/

Recommended Extensions:

* Python
* Jupyter

---

# 2. Create Project Structure

```text
pandas-learning/
│
├── data/
├── notebooks/
├── scripts/
├── outputs/
├── requirements.txt
└── README.md
```

---

# 3. Create Virtual Environment

## Windows

```bash
python -m venv venv
venv\Scripts\activate
```

## Mac/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

# 4. Install Required Libraries

```bash
pip install pandas numpy matplotlib seaborn jupyter pyarrow openpyxl
```

Save dependencies:

```bash
pip freeze > requirements.txt
```

---

# 5. Start Jupyter Notebook

```bash
jupyter notebook
```

---

# 6. Download Datasets

## Beginner Datasets

### Titanic Dataset

https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv

### Iris Dataset

https://archive.ics.uci.edu/ml/datasets/iris

### Netflix Dataset

https://www.kaggle.com/datasets/shivamb/netflix-shows

---

## Intermediate Datasets

### NYC Taxi Dataset

https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

### COVID-19 Dataset

https://github.com/CSSEGISandData/COVID-19

---

## Advanced Datasets

### Yahoo Finance

https://github.com/ranaroussi/yfinance

### OpenML

https://www.openml.org

---

# 7. First Pandas Notebook

Create:

```text
notebooks/01_pandas_basics.ipynb
```

---

# 8. Load Dataset

```python
import pandas as pd
import numpy as np

df = pd.read_csv("../data/titanic.csv")

df.head()
```

---

# 9. Basic Pandas Operations

## View Shape

```python
df.shape
```

## View Columns

```python
df.columns
```

## Select Columns

```python
df[["Name", "Age", "Sex"]]
```

## Filter Rows

```python
df[df["Age"] > 18]
```

## Sort Values

```python
df.sort_values("Fare", ascending=False)
```

---

# 10. Missing Values

```python
df.isnull().sum()
```

Fill missing values:

```python
df["Age"] = df["Age"].fillna(df["Age"].median())
```

---

# 11. GroupBy Operations

```python
df.groupby("Sex")["Survived"].mean()
```

---

# 12. NumPy Basics

Create:

```text
notebooks/02_numpy_basics.ipynb
```

---

## NumPy Arrays

```python
import numpy as np

arr = np.array([1, 2, 3, 4])

print(arr)
```

---

## Vectorized Operations

```python
arr * 10
```

---

## Statistics

```python
arr.mean()
arr.std()
arr.max()
```

---

## Matrix Operations

```python
matrix = np.array([
    [1, 2],
    [3, 4]
])

matrix.T
```

---

# 13. Intermediate Pandas Skills

## Datetime Operations

```python
df["date"] = pd.to_datetime(df["date"])

df["year"] = df["date"].dt.year
```

---

## String Cleaning

```python
df["title"] = (
    df["title"]
    .str.lower()
    .str.strip()
)
```

---

## Merging DataFrames

```python
merged = pd.merge(df1, df2, on="id")
```

---

## Pivot Tables

```python
pivot = df.pivot_table(
    values="sales",
    index="region",
    columns="category",
    aggfunc="sum"
)
```

---

# 14. Visualization

```python
import matplotlib.pyplot as plt

df["Age"].hist()

plt.show()
```

---

# 15. Advanced Pandas

## Method Chaining

```python
(
    df
    .dropna()
    .query("sales > 100")
    .groupby("region")
    .agg(total_sales=("sales", "sum"))
)
```

---

## Read Large CSV in Chunks

```python
chunks = pd.read_csv(
    "../data/large_file.csv",
    chunksize=100000
)

for chunk in chunks:
    print(chunk.shape)
```

---

## Save as Parquet

```python
df.to_parquet("../data/output.parquet")
```

---

## Read Parquet

```python
df = pd.read_parquet("../data/output.parquet")
```

---

# 16. Performance Optimization

## Optimize Memory

```python
df["category"] = df["category"].astype("category")
```

---

# 17. Industry Best Practices

## Use Relative Paths

Good:

```python
pd.read_csv("../data/file.csv")
```

Avoid:

```python
pd.read_csv("C:/Users/xyz/Desktop/file.csv")
```

---

## Avoid Loops

Bad:

```python
for i in range(len(df)):
    df.loc[i, "x"] *= 2
```

Good:

```python
df["x"] *= 2
```

---

## Use Reusable Functions

```python
def clean_columns(df):
    df.columns = df.columns.str.lower()
    return df
```

---

# 18. Recommended Notebook Structure

```text
01_numpy_basics.ipynb
02_pandas_basics.ipynb
03_data_cleaning.ipynb
04_groupby_aggregation.ipynb
05_merging_joining.ipynb
06_visualization.ipynb
07_large_data_processing.ipynb
08_project_titanic_analysis.ipynb
09_project_netflix_analysis.ipynb
```

---

# 19. Weekly Learning Plan

## Week 1

* Python basics
* NumPy arrays

## Week 2

* pandas basics
* filtering
* sorting

## Week 3

* missing values
* groupby
* aggregation

## Week 4

* joins
* merges
* pivot tables

## Week 5

* datetime operations
* string cleaning

## Week 6

* visualization
* mini project

## Week 7

* optimization
* parquet
* chunk processing

## Week 8+

* advanced projects
* portfolio building

---

# 20. Recommended Projects

## Beginner

* Titanic survival analysis
* Iris analysis

## Intermediate

* Netflix analytics
* COVID trend analysis

## Advanced

* Stock market analytics
* Fraud detection preprocessing
* Large-scale data pipelines

---

# 21. Golden Rule

Master:

* cleaning messy data
* groupby operations
* joins
* vectorization
* optimization
* reproducible workflows

These are the exact skills used in production analytics and data science workflows.
