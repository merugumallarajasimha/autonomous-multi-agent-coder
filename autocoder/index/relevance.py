# autocoder/index/relevance.py
import re
from typing import List, Tuple, Dict, Any, Set


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase words, splitting on whitespace and punctuation."""
    # Split on non-alphanumeric characters (including underscores, dots, etc.)
    tokens = re.split(r"[^\w]+", text.lower())
    # Filter out empty strings and very short tokens (< 2 chars)
    return {t for t in tokens if len(t) >= 2}


def score_relevance(user_request: str, repo_map: Dict[str, Any]) -> List[Tuple[str, float]]:
    """Deterministic, non-LLM relevance scoring. For each file in
    repo_map["files"], compute a score based on:
    - Keyword overlap between user_request (lowercased, tokenized on
      whitespace/punctuation) and: the file path itself, class names,
      function names, and import names for that file (from
      repo_map["symbols"])
    - Give higher weight to matches in class/function names than to matches
      in the file path alone
    - Files with zero keyword overlap get a score of 0.0 — do not assign an
      arbitrary baseline score to unrelated files
    Return a list of (file_path, score) tuples sorted descending by score.
    This is intentionally simple keyword matching, not semantic search —
    document that limitation in a comment."""
    
    # This is intentionally simple keyword matching, not semantic search.
    # It does not understand synonyms, context, or intent - only exact token overlap.
    
    request_tokens = _tokenize(user_request)
    if not request_tokens:
        return []
    
    files = repo_map.get("files", [])
    symbols = repo_map.get("symbols", {})
    
    scored: List[Tuple[str, float]] = []
    
    for file_info in files:
        file_path = file_info["path"]
        file_symbols = symbols.get(file_path, {})
        
        # Collect all searchable text for this file
        file_path_tokens = _tokenize(file_path)
        
        # Class names
        class_names = [c.get("name", "") for c in file_symbols.get("classes", [])]
        class_tokens = set()
        for name in class_names:
            class_tokens.update(_tokenize(name))
        
        # Function names
        func_names = [f.get("name", "") for f in file_symbols.get("functions", [])]
        func_tokens = set()
        for name in func_names:
            func_tokens.update(_tokenize(name))
        
        # Import names (just the module parts)
        import_names = file_symbols.get("imports", [])
        import_tokens = set()
        for imp in import_names:
            import_tokens.update(_tokenize(imp))
        
        # Calculate overlaps
        path_overlap = len(request_tokens & file_path_tokens)
        class_overlap = len(request_tokens & class_tokens)
        func_overlap = len(request_tokens & func_tokens)
        import_overlap = len(request_tokens & import_tokens)
        
        total_overlap = path_overlap + class_overlap + func_overlap + import_overlap
        
        if total_overlap == 0:
            score = 0.0
        else:
            # Weighted scoring: class/function names > imports > file path
            score = (
                class_overlap * 3.0 +      # Highest weight - class names are most descriptive
                func_overlap * 2.5 +       # Functions are very descriptive
                import_overlap * 1.5 +     # Imports show relationships
                path_overlap * 1.0         # File path alone is weakest signal
            )
        
        scored.append((file_path, score))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def select_relevant_files(
    user_request: str,
    repo_map: Dict[str, Any],
    max_files: int = 8,
    min_score: float = 0.0
) -> List[str]:
    """Calls score_relevance() and returns the top-scoring file paths, up to
    max_files, excluding any with score <= min_score. If FEWER than 2 files
    score above min_score, this is a signal the keyword match failed to find
    anything meaningful — in that case, return an empty list rather than
    padding with irrelevant files, so the caller can decide to fall back to
    reading everything instead of proceeding with a bad filter."""
    scored = score_relevance(user_request, repo_map)
    
    # Filter by min_score
    filtered = [(path, score) for path, score in scored if score > min_score]
    
    # If fewer than 2 files have meaningful scores, return empty list
    if len(filtered) < 2:
        return []
    
    # Return top max_files
    return [path for path, _ in filtered[:max_files]]