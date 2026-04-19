"""
PySpark Engine for Automated EDA Platform
==========================================
A full-featured PySpark processing engine that mirrors the Polars engine
but uses Apache Spark for distributed computing on truly massive datasets.

Each function corresponds to a PySpark operation category from the user's reference list.
"""

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    DoubleType, FloatType, BooleanType
)
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


# ============================================================
# 🔹 1. BASIC SETUP — SparkSession Initialization
# ============================================================

def get_spark():
    """
    Entry point for all Spark operations.
    Creates or returns the active SparkSession.
    .master("local[*]") uses all available CPU cores for local mode.
    """
    spark = SparkSession.builder \
        .appName("DataEngineerPro") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_csv(filepath: str):
    """
    read.csv() — Load CSV data into a Spark DataFrame.
    inferSchema=True automatically detects column types.
    header=True uses the first row as column names.
    """
    spark = get_spark()
    return spark.read.csv(filepath, header=True, inferSchema=True)


def load_parquet(filepath: str):
    """Load a Parquet file into a Spark DataFrame."""
    spark = get_spark()
    return spark.read.parquet(filepath)


def get_schema_info(sdf):
    """
    printSchema() / schema() — Returns schema as a structured dict.
    """
    schema_info = []
    for field in sdf.schema.fields:
        schema_info.append({
            "column": field.name,
            "type": str(field.dataType),
            "nullable": field.nullable
        })
    return schema_info


def get_preview(sdf, n=5):
    """
    show() equivalent — Returns the first n rows as a list of dicts.
    """
    return [row.asDict() for row in sdf.head(n)]


# ============================================================
# 🔹 2. FILTERING & CLEANING
# ============================================================

def filter_rows(sdf, column: str, operator: str, value):
    """
    filter() / where() — Filter rows based on a condition.
    Supports operators: >, <, >=, <=, ==, !=
    """
    col = F.col(column)
    if operator == ">":
        return sdf.filter(col > value)
    elif operator == "<":
        return sdf.filter(col < value)
    elif operator == ">=":
        return sdf.filter(col >= value)
    elif operator == "<=":
        return sdf.filter(col <= value)
    elif operator == "==":
        return sdf.filter(col == value)
    elif operator == "!=":
        return sdf.filter(col != value)
    return sdf


def drop_nulls(sdf, subset=None):
    """
    dropna() — Remove rows with null values.
    If subset is provided, only checks those columns.
    """
    if subset:
        return sdf.dropna(subset=subset)
    return sdf.dropna()


def fill_nulls(sdf, column: str, strategy: str = "mean"):
    """
    fillna() — Fill null values with a computed value.
    Strategies: mean, median, mode, zero, custom
    """
    if strategy == "mean":
        mean_val = sdf.select(F.mean(column)).collect()[0][0]
        return sdf.fillna({column: mean_val})
    elif strategy == "median":
        median_val = sdf.approxQuantile(column, [0.5], 0.01)[0]
        return sdf.fillna({column: median_val})
    elif strategy == "mode":
        mode_val = sdf.groupBy(column).count().orderBy(F.desc("count")).first()[0]
        return sdf.fillna({column: mode_val})
    elif strategy == "zero":
        return sdf.fillna({column: 0})
    return sdf


def replace_values(sdf, column: str, old_value, new_value):
    """
    replace() — Replace specific values in a column.
    e.g., replace "NA" with None, or "Unknown" with "Other"
    """
    return sdf.withColumn(
        column,
        F.when(F.col(column) == old_value, new_value).otherwise(F.col(column))
    )


def drop_duplicates(sdf, subset=None):
    """
    dropDuplicates() — Remove duplicate rows.
    If subset is provided, only considers those columns for uniqueness.
    """
    if subset:
        return sdf.dropDuplicates(subset=subset)
    return sdf.dropDuplicates()


# ============================================================
# 🔹 3. COLUMN OPERATIONS
# ============================================================

def select_columns(sdf, columns: list):
    """
    select() — Select specific columns from the DataFrame.
    """
    return sdf.select(*columns)


def add_or_modify_column(sdf, column: str, expression: str):
    """
    withColumn() — Create or modify a column.
    Common expressions: log, sqrt, square, abs, reciprocal
    """
    if expression == "log":
        return sdf.withColumn(column, F.log1p(F.col(column)))
    elif expression == "sqrt":
        return sdf.withColumn(column, F.sqrt(F.abs(F.col(column))))
    elif expression == "square":
        return sdf.withColumn(column, F.pow(F.col(column), 2))
    elif expression == "abs":
        return sdf.withColumn(column, F.abs(F.col(column)))
    elif expression == "reciprocal":
        return sdf.withColumn(
            column,
            F.when(F.col(column) != 0, 1.0 / F.col(column)).otherwise(None)
        )
    return sdf


def drop_column(sdf, column: str):
    """
    drop() — Drop a column from the DataFrame.
    """
    return sdf.drop(column)


def rename_column(sdf, old_name: str, new_name: str):
    """
    alias() — Rename a column.
    """
    return sdf.withColumnRenamed(old_name, new_name)


def cast_column(sdf, column: str, new_type: str):
    """
    cast() — Change column data type.
    Supports: int, float, double, string, boolean
    """
    type_map = {
        "int": IntegerType(),
        "float": FloatType(),
        "double": DoubleType(),
        "string": StringType(),
        "boolean": BooleanType(),
    }
    target = type_map.get(new_type.lower())
    if target:
        return sdf.withColumn(column, F.col(column).cast(target))
    return sdf


def conditional_column(sdf, new_col: str, condition_col: str, threshold, 
                       true_val="High", false_val="Low"):
    """
    when().otherwise() — Conditional column logic (like if-else).
    Example: Create a "Risk" column where Age > 60 = "High", else "Low"
    """
    return sdf.withColumn(
        new_col,
        F.when(F.col(condition_col) > threshold, true_val).otherwise(false_val)
    )


# ============================================================
# 🔹 4. AGGREGATION & GROUPING
# ============================================================

def group_and_aggregate(sdf, group_cols: list, agg_dict: dict):
    """
    groupBy().agg() — Group data and apply multiple aggregations.
    
    agg_dict format: {"column_name": "operation"}
    e.g., {"Sales": "sum", "Age": "avg", "Orders": "count"}
    """
    agg_exprs = []
    for col_name, op in agg_dict.items():
        if op == "sum":
            agg_exprs.append(F.sum(col_name).alias(f"{col_name}_sum"))
        elif op == "avg" or op == "mean":
            agg_exprs.append(F.avg(col_name).alias(f"{col_name}_avg"))
        elif op == "count":
            agg_exprs.append(F.count(col_name).alias(f"{col_name}_count"))
        elif op == "min":
            agg_exprs.append(F.min(col_name).alias(f"{col_name}_min"))
        elif op == "max":
            agg_exprs.append(F.max(col_name).alias(f"{col_name}_max"))
        elif op == "stddev":
            agg_exprs.append(F.stddev(col_name).alias(f"{col_name}_stddev"))
    
    return sdf.groupBy(*group_cols).agg(*agg_exprs)


def simple_count(sdf):
    """count() — Count total rows."""
    return sdf.count()


# ============================================================
# 🔹 5. SORTING
# ============================================================

def sort_data(sdf, column: str, ascending: bool = True):
    """
    orderBy() / sort() — Sort DataFrame by column.
    """
    if ascending:
        return sdf.orderBy(F.col(column).asc())
    else:
        return sdf.orderBy(F.col(column).desc())


# ============================================================
# 🔹 6. JOINS
# ============================================================

def join_dataframes(sdf1, sdf2, on_column: str, how: str = "inner"):
    """
    join() — Combine two DataFrames on a column/key.
    Supported types: inner, left, right, outer, cross, semi, anti
    """
    return sdf1.join(sdf2, on=on_column, how=how)


# ============================================================
# 🔹 7. WINDOW FUNCTIONS
# ============================================================

def add_row_number(sdf, partition_col: str, order_col: str):
    """
    row_number() — Add a sequential row number within each partition.
    Window.partitionBy().orderBy()
    """
    window_spec = Window.partitionBy(partition_col).orderBy(order_col)
    return sdf.withColumn("row_number", F.row_number().over(window_spec))


def add_rank(sdf, partition_col: str, order_col: str, rank_type: str = "rank"):
    """
    rank(), dense_rank() — Add ranking column within partitions.
    """
    window_spec = Window.partitionBy(partition_col).orderBy(F.desc(order_col))
    if rank_type == "rank":
        return sdf.withColumn("rank", F.rank().over(window_spec))
    elif rank_type == "dense_rank":
        return sdf.withColumn("dense_rank", F.dense_rank().over(window_spec))
    return sdf


def add_lag_lead(sdf, partition_col: str, order_col: str, 
                 target_col: str, offset: int = 1, func: str = "lag"):
    """
    lag() / lead() — Access previous or next row values.
    Useful for time-series comparisons (e.g., month-over-month changes).
    """
    window_spec = Window.partitionBy(partition_col).orderBy(order_col)
    if func == "lag":
        return sdf.withColumn(f"{target_col}_lag_{offset}", F.lag(target_col, offset).over(window_spec))
    elif func == "lead":
        return sdf.withColumn(f"{target_col}_lead_{offset}", F.lead(target_col, offset).over(window_spec))
    return sdf


def add_running_total(sdf, partition_col: str, order_col: str, sum_col: str):
    """
    Running/Cumulative sum using Window functions.
    """
    window_spec = Window.partitionBy(partition_col).orderBy(order_col).rowsBetween(
        Window.unboundedPreceding, Window.currentRow
    )
    return sdf.withColumn(f"{sum_col}_cumsum", F.sum(sum_col).over(window_spec))


# ============================================================
# 🔹 8. UDFs (User Defined Functions)
# ============================================================

def apply_udf_example(sdf, column: str, func_type: str = "upper"):
    """
    udf() — Apply custom Python logic to columns.
    Demonstrates UDF registration without actual custom user code.
    Pre-built functions: upper, lower, length, reverse
    """
    if func_type == "upper":
        return sdf.withColumn(column, F.upper(F.col(column)))
    elif func_type == "lower":
        return sdf.withColumn(column, F.lower(F.col(column)))
    elif func_type == "length":
        return sdf.withColumn(f"{column}_length", F.length(F.col(column)))
    elif func_type == "reverse":
        return sdf.withColumn(column, F.reverse(F.col(column)))
    return sdf


# ============================================================
# 🔹 9. SAVING DATA
# ============================================================

def save_as_csv(sdf, path: str, mode: str = "overwrite"):
    """
    write.csv() — Save DataFrame as CSV.
    mode: overwrite, append, ignore, error
    """
    sdf.coalesce(1).write.mode(mode).option("header", "true").csv(path)
    return path


def save_as_parquet(sdf, path: str, mode: str = "overwrite"):
    """
    write.parquet() — Save as Parquet (efficient columnar format).
    """
    sdf.write.mode(mode).parquet(path)
    return path


# ============================================================
# 🔹 10. DESCRIPTIVE STATS
# ============================================================

def describe_data(sdf, columns: list = None):
    """
    describe() — Summary statistics (count, mean, stddev, min, max).
    Returns results as a list of dicts for the frontend.
    """
    if columns:
        desc_df = sdf.select(*columns).describe()
    else:
        desc_df = sdf.describe()
    return [row.asDict() for row in desc_df.collect()]


def summary_data(sdf, columns: list = None):
    """
    summary() — Extended summary with additional metrics like 25%, 50%, 75% percentiles.
    """
    if columns:
        summ_df = sdf.select(*columns).summary()
    else:
        summ_df = sdf.summary()
    return [row.asDict() for row in summ_df.collect()]


# ============================================================
# 🔹 BONUS: SPARK EDA (Full Analysis Pipeline)
# ============================================================

def spark_perform_analysis(sdf):
    """
    Runs a full EDA audit on a Spark DataFrame.
    Returns stats, audit list, numeric/categorical columns, and shape.
    Mirrors the Polars perform_analysis() function output format.
    """
    total_rows = sdf.count()
    total_cols = len(sdf.columns)
    
    # Identify numeric and categorical columns
    num_cols = [f.name for f in sdf.schema.fields 
                if isinstance(f.dataType, (IntegerType, DoubleType, FloatType))]
    cat_cols = [f.name for f in sdf.schema.fields 
                if isinstance(f.dataType, (StringType, BooleanType))]
    
    # Build audit
    audit = []
    for col_name in sdf.columns:
        null_count = sdf.filter(F.col(col_name).isNull()).count()
        null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0
        unique_count = sdf.select(col_name).distinct().count()
        
        # Check for missing values
        if null_pct > 0:
            severity = f"{null_pct}% Null"
            if null_pct > 20:
                action = "⚠️ Consider dropping column or heavy imputation"
            else:
                action = "💡 Fill with Mean/Median/Mode"
            audit.append({
                "feature": col_name,
                "issue": "Missing Values",
                "severity": severity,
                "action": action
            })
        
        # Check for skewness (numeric only)
        if col_name in num_cols:
            try:
                skew_val = sdf.select(F.skewness(col_name)).collect()[0][0]
                if skew_val is not None and abs(skew_val) > 1.5:
                    audit.append({
                        "feature": col_name,
                        "issue": "High Skew",
                        "severity": f"Skewness: {round(skew_val, 2)}",
                        "action": "💡 Apply Log/Sqrt Transform"
                    })
            except Exception:
                pass
        
        # Check for constant columns
        if unique_count <= 1:
            audit.append({
                "feature": col_name,
                "issue": "Constant/Zero Variance",
                "severity": "Danger",
                "action": "🗑️ Drop this column"
            })
    
    # Stats
    stats_rows = []
    if num_cols:
        desc = sdf.select(*num_cols).describe().collect()
        for row in desc:
            stats_rows.append(row.asDict())
    
    return {
        "stats": stats_rows,
        "audit": audit,
        "shape": [total_rows, total_cols],
        "num_cols": num_cols,
        "cat_cols": cat_cols,
    }


def spark_apply_transformation(sdf, column: str, transform_type: str):
    """
    Applies transformations using PySpark functions.
    Mirrors apply_custom_transformation() from the Polars engine.
    """
    if transform_type == "log":
        return sdf.withColumn(column, F.log1p(F.col(column)))
    elif transform_type == "sqrt":
        return sdf.withColumn(column, F.sqrt(F.abs(F.col(column))))
    elif transform_type == "square":
        return sdf.withColumn(column, F.pow(F.col(column), 2))
    elif transform_type == "abs":
        return sdf.withColumn(column, F.abs(F.col(column)))
    elif transform_type == "reciprocal":
        return sdf.withColumn(
            column,
            F.when(F.col(column) != 0, 1.0 / F.col(column)).otherwise(None)
        )
    elif transform_type == "standard_scale":
        stats = sdf.select(F.mean(column), F.stddev(column)).collect()[0]
        mean_val, std_val = stats[0], stats[1]
        if std_val and std_val > 0:
            return sdf.withColumn(column, (F.col(column) - mean_val) / std_val)
        return sdf
    elif transform_type == "minmax_scale":
        stats = sdf.select(F.min(column), F.max(column)).collect()[0]
        min_val, max_val = stats[0], stats[1]
        if max_val != min_val:
            return sdf.withColumn(column, (F.col(column) - min_val) / (max_val - min_val))
        return sdf
    elif transform_type == "fill_mean":
        mean_val = sdf.select(F.mean(column)).collect()[0][0]
        return sdf.fillna({column: mean_val})
    elif transform_type == "fill_median":
        median_val = sdf.approxQuantile(column, [0.5], 0.01)[0]
        return sdf.fillna({column: median_val})
    elif transform_type == "fill_mode":
        mode_val = sdf.groupBy(column).count().orderBy(F.desc("count")).first()
        if mode_val:
            return sdf.fillna({column: mode_val[0]})
        return sdf
    elif transform_type == "cap_outliers_iqr":
        quantiles = sdf.approxQuantile(column, [0.25, 0.75], 0.01)
        q1, q3 = quantiles[0], quantiles[1]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return sdf.withColumn(
            column,
            F.when(F.col(column) < lower, lower)
             .when(F.col(column) > upper, upper)
             .otherwise(F.col(column))
        )
    elif transform_type == "drop_duplicates":
        return sdf.dropDuplicates()
    elif transform_type == "drop_nulls":
        return sdf.dropna(subset=[column])
    
    return sdf


def stop_spark():
    """Gracefully shut down the SparkSession."""
    spark = get_spark()
    spark.stop()
