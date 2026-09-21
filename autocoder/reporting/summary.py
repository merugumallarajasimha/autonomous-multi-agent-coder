# autocoder/reporting/summary.py
import sys


def render_summary_report(run_data: dict) -> str:
    """Takes the final run-report dict and returns a formatted box string."""
    
    # Check if we can use box-drawing characters (UTF-8 support)
    use_box_chars = sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower()
    
    if use_box_chars:
        # Box-drawing characters for UTF-8 terminals
        TL, TR, BL, BR = "╔", "╗", "╚", "╝"
        H, V = "═", "║"
        T, B = "╠", "╣"
    else:
        # ASCII fallback for Windows consoles
        TL, TR, BL, BR = "+", "+", "+", "+"
        H, V = "-", "|"
        T, B = "+", "+"
    
    # Define the fields to display with their keys and labels
    fields = [
        ("Status", "status"),
        ("Tasks", "tasks_completed"),
        ("Files modified", "files_modified"),
        ("Tests passed", "tests_passed"),
        ("Tests failed", "tests_failed"),
        ("Fix iterations", "fix_iterations"),
        ("Review issues", "review_issues_resolved"),
        ("Sandbox", "sandbox_type"),
        ("Git status", "git_status"),
    ]
    
    # Build the lines with values from run_data
    lines = []
    for label, key in fields:
        value = run_data.get(key)
        if value is None:
            display = "N/A"
        elif key == "files_modified" and isinstance(value, list):
            display = str(len(value))
        elif key == "review_issues_resolved" and isinstance(value, int):
            display = f"{value} resolved"
        else:
            display = str(value)
        lines.append(f"{label:<18} {display}")
    
    # Calculate the content width (longest line)
    max_content_width = max(len(line) for line in lines)
    box_width = max_content_width + 4  # 2 spaces padding each side
    
    # Build box
    top = TL + H * box_width + TR
    title_line = V + " AUTONOMOUS CODING REPORT ".center(box_width) + V
    separator = T + H * box_width + B
    
    content_lines = []
    for line in lines:
        padding = box_width - len(line)
        content_lines.append(V + " " + line + " " * padding + " " + V)
    
    bottom = BL + H * box_width + BR
    
    return "\n".join([top, title_line, separator] + content_lines + [bottom])