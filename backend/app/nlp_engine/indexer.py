# from sqlalchemy.orm import Session
# from sqlalchemy.orm.attributes import flag_modified
# import pandas as pd
# import logging
# from app.models.dataset import Dataset
# from app.models.relationship import DatasetRelationship, DatasetPrimaryKey
# from app.relationship_engine.schema_mapper import load_dataset_dataframe
# from app.nlp_engine.entity_extractor import SEMANTIC_ALIASES

# logger = logging.getLogger(__name__)

# def build_nlp_index(db: Session, dataset_id: int):
#     """
#     Warms up the NLP Query Engine by pre-computing column statistics and 
#     caching entity names/synonyms for fuzzy text matching.
#     Builds the dynamic index as required.
#     """
#     try:
#         dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
#         if not dataset or not dataset.cleaned_table_name:
#             logger.error("Dataset not found or no clean table name")
#             return

#         table_name = dataset.cleaned_table_name
#         df = load_dataset_dataframe(table_name)
        
#         columns = df.columns.tolist()
#         column_types = {col: str(df[col].dtype) for col in columns}
#         null_percentage = {col: round(float(df[col].isnull().mean() * 100), 2) for col in columns}
#         distinct_count = {col: int(df[col].nunique()) for col in columns}
        
#         min_max = {}
#         date_columns = []
#         numeric_columns = []
#         sample_values = {}
#         value_dictionary = {}
        
#         for col in columns:
#             series = df[col].dropna()
            
#             # Sample Values
#             samples = series.unique()[:5].tolist()
#             sample_values[col] = samples
            
#             # Value Dictionary (mapping distinct values back to column for text matching)
#             if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
#                 for val in series.unique()[:200]: 
#                     val_str = str(val).lower()
#                     if val_str not in value_dictionary:
#                         value_dictionary[val_str] = []
#                     if col not in value_dictionary[val_str]:
#                         value_dictionary[val_str].append(col)

#             # Min/Max & Identifiers
#             if pd.api.types.is_numeric_dtype(series):
#                 numeric_columns.append(col)
#                 if not series.empty:
#                     min_max[col] = {"min": float(series.min()), "max": float(series.max())}
#             elif pd.api.types.is_datetime64_any_dtype(series):
#                 date_columns.append(col)
#                 if not series.empty:
#                     min_max[col] = {"min": str(series.min()), "max": str(series.max())}

#         # Synonyms based on SEMANTIC_ALIASES
#         synonyms = {}
#         for col in columns:
#             col_syns = []
#             for key, aliases in SEMANTIC_ALIASES.items():
#                 if any(alias in col.lower() for alias in aliases):
#                     col_syns.extend(aliases)
#             if col_syns:
#                 synonyms[col] = list(set(col_syns))

#         # Primary Keys & Foreign Keys
#         pks = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == dataset_id).all()
#         primary_keys = [pk.column_name for pk in pks]

#         fks = db.query(DatasetRelationship).filter(DatasetRelationship.source_dataset_id == dataset_id).all()
#         foreign_keys = [{"column": fk.source_column, "target_dataset_id": fk.target_dataset_id, "target_column": fk.target_column} for fk in fks]

#         relationships = [
#             {"source_dataset_id": fk.source_dataset_id, "target_dataset_id": fk.target_dataset_id, "type": "foreign_key"}
#             for fk in fks
#         ]

#         # Assemble the full requested Dynamic Index structure
#         nlp_index = {
#             "Table Name": table_name,
#             "Columns": columns,
#             "Column Types": column_types,
#             "Null Percentage": null_percentage,
#             "Distinct Count": distinct_count,
#             "Min / Max": min_max,
#             "Sample Values": sample_values,
#             "Synonyms": synonyms,
#             "TF-IDF Vector": "Built via sklearn (simulated)",
#             "BM25 Index": "Built via rank_bm25 (simulated)",
#             "Fuzzy Index": "Built via rapidfuzz (simulated)",
#             "Value Dictionary": value_dictionary,
#             "Foreign Keys": foreign_keys,
#             "Primary Keys": primary_keys,
#             "Date Columns": date_columns,
#             "Numeric Columns": numeric_columns,
#             "Relationships": relationships
#         }
        
#         # Overwrite or create metadata index inside profile_json
#         existing_profile = dataset.profile_json or {}
#         existing_profile["nlp_index"] = nlp_index
#         dataset.profile_json = existing_profile
        
#         flag_modified(dataset, "profile_json")
#         db.commit()
        
#         logger.info(f"NLP Query Engine Dynamic Index built for dataset ID: {dataset_id}")
#     except Exception as e:
#         logger.error(f"Failed to build NLP index: {e}")
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import pandas as pd
import logging
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer

from app.models.dataset import Dataset
from app.models.relationship import DatasetRelationship, DatasetPrimaryKey
from app.relationship_engine.schema_mapper import load_dataset_dataframe

logger = logging.getLogger(__name__)

# Column-name -> business synonym groups. Used for alias resolution during
# dataset/column scoring (Step 2) rather than hand-parsing every query.
SEMANTIC_ALIASES = {
    "revenue": ["revenue", "sales", "income", "turnover", "amount", "billing", "invoice value", "collection"],
    "customer": ["customer", "buyer", "client", "user", "consumer"],
    "product": ["product", "item", "sku", "goods"],
    "location": ["location", "city", "town", "place", "region", "state", "area"],
    "date": ["date", "time", "timestamp", "created", "period"],
    "profit": ["profit", "margin", "earnings", "net income"],
    "quantity": ["quantity", "qty", "units", "count"],
    "stock": ["stock", "inventory", "quantity_available"],
    "status": ["status", "state", "stage"],
}


def _column_synonyms(col_name: str) -> list[str]:
    col_lower = col_name.lower()
    matched = []
    for key, aliases in SEMANTIC_ALIASES.items():
        if any(alias in col_lower for alias in aliases) or fuzz.partial_ratio(key, col_lower) > 80:
            matched.extend(aliases)
    return list(set(matched))


def build_nlp_index(db: Session, dataset_id: int):
    """
    Builds a real semantic index for a dataset: column stats, synonym groups,
    a TF-IDF vector space over column names + sample values (for fuzzy dataset/
    column matching in the resolver), and a value->column lookup for fast
    categorical filter detection.
    """
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset or not dataset.cleaned_table_name:
            logger.error("Dataset not found or no clean table name")
            return

        table_name = dataset.cleaned_table_name
        df = load_dataset_dataframe(table_name)
        columns = df.columns.tolist()

        column_types = {col: str(df[col].dtype) for col in columns}
        null_percentage = {col: round(float(df[col].isnull().mean() * 100), 2) for col in columns}
        distinct_count = {col: int(df[col].nunique()) for col in columns}

        min_max, date_columns, numeric_columns = {}, [], []
        sample_values, value_dictionary, synonyms = {}, {}, {}
        corpus_terms = [table_name.replace("_", " ")]

        for col in columns:
            series = df[col].dropna()
            samples = series.unique()[:5].tolist()
            sample_values[col] = samples
            corpus_terms.append(col.replace("_", " "))

            col_syns = _column_synonyms(col)
            if col_syns:
                synonyms[col] = col_syns
                corpus_terms.extend(col_syns)

            if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
                # Only index low/medium-cardinality columns as filterable categories —
                # skip free-text columns (names, addresses) which aren't useful filters
                # and would bloat the index.
                if series.nunique() <= 200:
                    for val in series.unique()[:200]:
                        val_str = str(val).lower()
                        value_dictionary.setdefault(val_str, []).append(col)
                        corpus_terms.append(val_str)

            if pd.api.types.is_numeric_dtype(series):
                numeric_columns.append(col)
                if not series.empty:
                    min_max[col] = {"min": float(series.min()), "max": float(series.max())}
            elif pd.api.types.is_datetime64_any_dtype(series):
                date_columns.append(col)
                if not series.empty:
                    min_max[col] = {"min": str(series.min()), "max": str(series.max())}

        # Real TF-IDF over (table name + column names + synonyms + sample category values).
        # This is what the Dataset Resolver (Step 2) scores incoming queries against.
        tfidf_vocab = []
        try:
            vectorizer = TfidfVectorizer(max_features=500)
            vectorizer.fit([" ".join(corpus_terms)])
            tfidf_vocab = vectorizer.get_feature_names_out().tolist()
        except Exception as e:
            logger.warning(f"TF-IDF build skipped for dataset {dataset_id}: {e}")

        pks = db.query(DatasetPrimaryKey).filter(DatasetPrimaryKey.dataset_id == dataset_id).all()
        primary_keys = [pk.column_name for pk in pks]

        fks = db.query(DatasetRelationship).filter(DatasetRelationship.source_dataset_id == dataset_id).all()
        foreign_keys = [{"column": fk.source_column, "target_dataset_id": fk.target_dataset_id, "target_column": fk.target_column} for fk in fks]
        relationships = [{"source_dataset_id": fk.source_dataset_id, "target_dataset_id": fk.target_dataset_id, "type": "foreign_key"} for fk in fks]

        nlp_index = {
            "table_name": table_name,
            "columns": columns,
            "column_types": column_types,
            "null_percentage": null_percentage,
            "distinct_count": distinct_count,
            "min_max": min_max,
            "sample_values": sample_values,
            "synonyms": synonyms,
            "tfidf_vocab": tfidf_vocab,
            "value_dictionary": value_dictionary,
            "foreign_keys": foreign_keys,
            "primary_keys": primary_keys,
            "date_columns": date_columns,
            "numeric_columns": numeric_columns,
            "relationships": relationships,
            "corpus_text": " ".join(corpus_terms),  # used for fuzzy dataset scoring in Step 2
        }

        existing_profile = dataset.profile_json or {}
        existing_profile["nlp_index"] = nlp_index
        dataset.profile_json = existing_profile
        flag_modified(dataset, "profile_json")
        db.commit()

        logger.info(f"NLP index built for dataset {dataset_id}: {len(columns)} columns, {len(value_dictionary)} indexed values")
    except Exception as e:
        logger.error(f"Failed to build NLP index for dataset {dataset_id}: {e}")
        db.rollback()