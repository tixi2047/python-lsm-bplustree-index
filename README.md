# 🌲 LSM-Tree

## 📖 About the Project

This project implements a lightweight database indexing and query engine in Python. It features a custom **Log-Structured Merge-tree (LSM)** index structure backed by multi-level **B+ trees** (`bplustree`) to efficiently handle insertions, updates, deletions, and complex structured queries over tabular datasets.

---

## ✨ Key Features

* 🗂️ **LSM Indexing:** Multi-level indexing (Level 0, Level 1, Level 2) with automated flushing and merge logic.
* 🔍 **Advanced Query Parser:** Supports logical conditions across multiple columns.
* 📊 **Aggregations:** Computes metrics like `AVG`, `MIN`, `MAX`, `SUM`, and `COUNT` on filtered row sets.
* 🛠️ **Interactive CLI Menu:** Easily insert rows manually, load bulk files, inspect tree levels, and execute dynamic queries.

---

## 🛠️ Prerequisites & Installation


The project requires the [`bplustree`](https://pypi.org/project/bplustree/) library.

### 1. Install Dependencies

Open your terminal and run the following command:

```bash
pip install bplustree
