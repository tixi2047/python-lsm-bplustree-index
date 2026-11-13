# pip install bplustree

import gc
import os
from bplustree import BPlusTree
import glob
import pickle
import time
import re

GREEN = '\033[92m'
TURQUOISE = '\033[96m'
RESET = '\033[0m'

def clear_previous_db_files(directory: str = "lsm_indexes"):
    """
    Deletes all .db, .db-wal, .db-shm files in the specified directory (default: lsm_indexes).
    """
    patterns = ["*.db", "*.db-wal", "*.db-shm"]
    if os.path.exists(directory):
        for pattern in patterns:
            for file_path in glob.glob(os.path.join(directory, pattern)):
                try:
                    os.remove(file_path)
                    #print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Could not delete {file_path}: {e}")
    


def str_to_int(s):
    return int.from_bytes(s.encode("utf-8"), byteorder="big")

def int_to_str(i):
    length = (i.bit_length() + 7) // 8
    return i.to_bytes(length, byteorder="big").decode("utf-8")

def check_fields_length(row_dict):
    for key in ["Name", "Gender", "Job"]:
        value = row_dict.get(key, "")
        if len(value) > 8:
            return False
    return True

def merge_lists_lsm_style(list1, list2):

    merged = list1 + list2
    result = []
    seen = set()
    skip_indices = set()  

    for i in range(len(merged) - 1, -1, -1): 
        x = merged[i]
        abs_x = abs(x)

        if i in skip_indices or abs_x in seen: continue

        for j in range(i - 1, -1, -1):
            if abs(merged[j]) == abs_x:
                skip_indices.add(j)

        seen.add(abs_x)
        result.append(x)

    return result

def add_indices(row, row_id):
    for col in index_columns:
        key = row.get(col)
        if key is not None:
            lsm_indexes[col].insert(key, row_id)
            lsm_indexes[col].flush_if_needed()

def delete_indices(row, row_id):
    for col in index_columns:
        old_key = row.get(col)
        lsm_indexes[col].insert(old_key, -row_id)


def insert_row(new_row, row_id):
    fact_table.fact_table_dict[row_id] = {k: v for k, v in new_row.items() if k != "ID"}
    add_indices(new_row, row_id)


def update_row(new_row, row_id, existing_row):
    delete_indices(existing_row, row_id)
    add_indices(new_row, row_id)
    fact_table.fact_table_dict[row_id] = {k: v for k, v in new_row.items() if k != "ID"}

  
class FactTable:
    """
    Loads table schema (column names) from FactTable.txt.
    """
    def __init__(self, schema_file: str = "FactTable.txt"):
        self.schema_file = schema_file
        self.columns = []
        self._load_schema()
        self.fact_table_dict = {}

    def _load_schema(self):
        try:
            with open(self.schema_file, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                self.columns = [col.strip() for col in line.split(",") if col.strip()]
        except Exception as e:
            print(f"Error loading schema: {e}")

    def get_columns(self):
        return self.columns
    
    def get_fact_table_dict(self):
        return self.fact_table_dict

    def load_data_as_dict(self, data_file: str = "input_data.txt"):
        """
        Loads all rows from input_data.txt, validates, and for each row:
        - If row exists, calls update_row
        - If not, calls insert_row
        """
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    values = [v.strip() for v in line.split(",")]
                    if len(values) != len(self.columns):
                        continue
                    row = {self.columns[i]: values[i] for i in range(len(self.columns))}
                    if not check_fields_length(row):
                        continue
                    row_id = int(row.get("ID", values[0]))
                    existing_row = fact_table.fact_table_dict.get(row_id)
                    if existing_row is None:
                        insert_row(row, row_id)
                    else:
                        update_row(row, row_id, existing_row)
        except Exception as e:
            print(f"Error loading data: {e}")



class LSMIndex:

    """
    Log Structured Merge (LSM) Tree Index with 3 levels.
    """
    def __init__(self, index_name: str):
        self.index_name = index_name
        self.levels = [0, 1, 2]
        self.capacities = {0: 10, 1: 20, 2: 9000}
        self.trees = {}

        index_dir = "lsm_indexes"
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
        for level in self.levels:
            tree_file = os.path.join(index_dir, f"{self.index_name}_Level_{level}.db")
            self.trees[level] = BPlusTree(tree_file, order=50, serializer=None)

    def _total_values(self, level):
        """
        Returns the total number of row_id values in the tree for the given level.
        """
        tree = self.trees[level]
        count = 0
        try:
            for value in tree.values():
                ids = pickle.loads(value)
                count += sum(1 for x in ids if x > 0)
        except Exception as e:
            pass
        return count

    def clear_level(self, level):

        try:
            tree = self.trees[level]
            self.trees[level] = None
            tree.close()
            gc.collect()
            

            index_dir = "lsm_indexes"
            base_name = f"{self.index_name}_Level_{level}.db"
            wal_name = f"{self.index_name}_Level_{level}.db-wal"
            shm_name = f"{self.index_name}_Level_{level}.db-shm"

            file_patterns = [base_name, wal_name, shm_name]
            for fname in file_patterns:
                file_path = os.path.join(index_dir, fname)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        #print(f"Deleted: {file_path}")
                    except Exception as e:
                        print(f"Could not delete {file_path}: {e}")

            time.sleep(0.1)
            tree_file = os.path.join(index_dir, base_name)
            self.trees[level] = BPlusTree(tree_file, order=50, serializer=None)

        except Exception as e:
            print(f"Error clearing level {level}: {e}")


    def insert(self, key, row_id):
        """
        Insert key-row_id pair into level 0 B+ tree.
        """
        key_int = str_to_int(str(key))
        tree0 = self.trees[0]
        if key_int in tree0:
            ids = pickle.loads(tree0[key_int])
            ids.append(row_id)
            tree0[key_int] = pickle.dumps(ids)
        else:
            tree0[key_int] = pickle.dumps([row_id])

    def flush_if_needed(self):

        for level in self.levels[:-1]:
            if self._total_values(level) == self.capacities[level]:
                self._flush_level(level, level + 1)
            else:
                break

    def _flush_level(self, from_level, to_level):
        from_tree = self.trees[from_level]
        to_tree = self.trees[to_level]
        is_last_level = (to_level == self.levels[-1])

        try:
            for key, from_value in from_tree.items():
                from_ids = pickle.loads(from_value)
                if key in to_tree:
                    to_ids = pickle.loads(to_tree[key])
                else:
                    to_ids = []

                merged = merge_lists_lsm_style(to_ids, from_ids)

                if is_last_level:
                    merged = [x for x in merged if x > 0]

                to_tree[key] = pickle.dumps(merged)

        except Exception as e:pass

        self.clear_level(from_level)


    def print_all_keys_and_values(self, level=0):
        """
        Prints all keys and their values from the specified level (default: 0).
        """
        tree = self.trees[level]
        print(f"\n=== LSMIndex: {self.index_name} Level {level} ===\n")
        try:
            for key_int, value in tree.items():
                try:
                    key_str = int_to_str(key_int)
                except Exception:
                    key_str = str(key_int)
                try:
                    ids = pickle.loads(value)
                except Exception:
                    ids = value
                print(f"{TURQUOISE}{key_str} => {ids}{RESET}")

        except Exception as e:
            pass



def parse_query(query):
    parts = query.split("AGG:")
    condition_part = parts[0].strip()
    agg_part = parts[1].strip()


    tokens = re.split(r'(\sAND\s|\sOR\s)', condition_part)

    conditions = []
    operators = []

    for token in tokens:
        token = token.strip()
        if token.upper() == "AND" or token.upper() == "OR":
            operators.append(token.upper())
        elif token:
            if "=" in token:
                field, values_str = token.split("=")
                values = [v.strip() for v in values_str.split(",")]
                conditions.append((field.strip(), values))

    agg_matches = re.findall(r'\(\s*(\w+)\s*,\s*(\w+)\s*\)', agg_part)
    aggregates = [(func.lower(), col) for func, col in agg_matches]

    return {
        "conditions": conditions,
        "operators": operators,
        "aggregates": aggregates
    }

def get_ids_for_value(col, value):
    key_int = str_to_int(value)
    all_ids = []

    for level in [0, 1, 2]:
        tree = lsm_indexes[col].trees[level]
        if key_int in tree:
            ids = pickle.loads(tree[key_int])
            if level == 0:
                all_ids = ids.copy()
                continue
            all_ids = merge_lists_lsm_style(ids, all_ids)

    return [x for x in all_ids if x > 0] 


def get_ids_for_condition(field, values):
    all_ids = []
    for value in values:
        ids = get_ids_for_value(field, value)
        all_ids = list(set(all_ids + ids))
    return all_ids


def combine_lists(list1, list2, operator):
    set1, set2 = set(list1), set(list2)
    if operator == "AND":
        return list(set1 & set2)
    elif operator == "OR":
        return list(set1 | set2)
    else:
        return []


def compute_aggregates(row_ids, aggregates):
    results = {}
    for func, col in aggregates:
        values = []
        for row_id in row_ids:
            row = fact_table.fact_table_dict.get(row_id)
            value = int(row.get(col))
            values.append(value)

        key = f"{func}({col})"

        if func == "avg":
            result = round(sum(values) / len(values),2)
        elif func == "min":
            result = min(values)
        elif func == "max":
            result = max(values)
        elif func == "sum":
            result = sum(values)
        elif func == "count":
            result = len(values)
        else:
            result = None
        results[key] = result
    return results



def get_ids_for_condition_no_index(field, values):
    matched_ids = []
    for row_id, row in fact_table.fact_table_dict.items():
        if str(row.get(field)) in values:
            matched_ids.append(row_id)
    return matched_ids


# MAIN EXECUTION:

clear_previous_db_files()
time.sleep(1) 
fact_table = FactTable("FactTable.txt")

index_columns = ["Name", "Gender", "Job"]
lsm_indexes = {col: LSMIndex(col) for col in index_columns}
print(f"\n=== FactTable Columns ===\n{GREEN}{fact_table.get_columns()}{RESET}")

while True:
    print(f"\n=== MENU ===\n")
    print(f"{GREEN}1. Inserting manually 1 row{RESET}")
    print(f"{GREEN}2. Insert from file...{RESET}")
    print(f"{GREEN}3. Delete row{RESET}")
    print(f"{GREEN}4. Query{RESET}")
    print(f"{GREEN}5. Print Level for Index{RESET}")
    print(f"{GREEN}6. Print ALL Levels for Index{RESET}")
    print(f"{GREEN}7. Print ALL Levels for ALL Indexes{RESET}")
    print(f"{GREEN}8. Exit{RESET}\n")

    try:
        option = int(input(f"{GREEN}Choose option: {RESET}").strip())
    except ValueError:
        continue

    if option == 8:
        print(f"{TURQUOISE}\nExiting...{RESET}")
        exit(0)

    elif option == 1:
        new_row = {}
        for col in fact_table.get_columns():
            value = input(f"{col}: ").strip()
            new_row[col] = value
        print(f"\n{TURQUOISE}Row: {new_row}{RESET}")

        if not check_fields_length(new_row):
            print(f"{TURQUOISE}\nTry again{RESET}")
            continue


        row_id = int(new_row.get("ID"))
        existing_row = fact_table.fact_table_dict.get(row_id)

        if existing_row is None:
            insert_row(new_row, row_id)
            print(f"{TURQUOISE}\nRow added{RESET}")
        else:
            update_row(new_row, row_id, existing_row)
            print(f"{TURQUOISE}\nRow updated{RESET}")

        

    elif option == 2:

        value= input(f"File path: ").strip()

        fact_table.load_data_as_dict(value)
        print(f"{TURQUOISE}\nFile processed{RESET}")


    elif option == 5:

        col = input(f"Index column (Name / Gender / Job): ").strip()
        level = int(input(f"Level (0 / 1 / 2): ").strip())
        lsm_indexes[col].print_all_keys_and_values(level=level)

    elif option == 3:

        row_id = int(input(f"Row ID to delete: ").strip())
        existing_row = fact_table.fact_table_dict.get(row_id)
        if existing_row is None:
            print(f"{TURQUOISE}\nRow ID = {row_id} does not exist{RESET}")
            continue
        delete_indices(existing_row, row_id)
        del fact_table.fact_table_dict[row_id]
        print(f"{TURQUOISE}\nRow ID = {row_id} deleted{RESET}")

    elif option == 6:

        col = input(f"Index column (Name / Gender / Job): ").strip()
        for level in [0, 1, 2]:
            lsm_indexes[col].print_all_keys_and_values(level=level)

    elif option == 7:

        for level in [0, 1, 2]:
            for col in index_columns:
                lsm_indexes[col].print_all_keys_and_values(level=level)

    elif option == 4:

        query = input(f"*Example: Name = Mike, David OR Gender = F AND Job = QA, Farmer AGG: (avg, Income), (min, Experience)\nEnter query: ").strip()
        parsed = parse_query(query)
        using_index = input(f"Using index? (y/n): ").strip().lower() == 'y'
        print(f"{TURQUOISE}\nParsed query: {parsed}{RESET}")

        conditions = parsed["conditions"]
        operators = parsed["operators"]
        aggregates = parsed["aggregates"]

        if not conditions:
            print(f"{TURQUOISE}\nNo conditions provided{RESET}")
            continue

        if using_index:
            result_ids = get_ids_for_condition(*conditions[0])
            for i in range(1, len(conditions)):
                operator = operators[i - 1]
                next_ids = get_ids_for_condition(*conditions[i])
                result_ids = combine_lists(result_ids, next_ids, operator)
        else:
            result_ids = get_ids_for_condition_no_index(*conditions[0])
            for i in range(1, len(conditions)):
                operator = operators[i - 1]
                next_ids = get_ids_for_condition_no_index(*conditions[i])
                result_ids = combine_lists(result_ids, next_ids, operator)

        if not result_ids:
            print(f"{TURQUOISE}\nNULL{RESET}")
        else:
            results = compute_aggregates(result_ids, aggregates)
            print(f"\n{TURQUOISE}Matching Row IDs: {result_ids}{RESET}")
            for k, v in results.items():
                print(f"\n{TURQUOISE}{k} = {v}{RESET}")
    else:
        continue

