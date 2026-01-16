
import csv
import statistics

def calculate_category_averages(file_path: str, start_year: int):
    """
    Calculates the 5-year average percentile (start_year and 4 years prior)
    for each category in JIF and JCI metrics.
    
    Args:
        file_path: Path to the CSV file.
        start_year: The starting year for the 5-year window.
        
    Returns:
        A dictionary with the structure:
        {
            "JIF": { "CATEGORY_NAME": average_percentile, ... },
            "JCI": { "CATEGORY_NAME": average_percentile, ... }
        }
    """
    
    # Data structure: data[metric][category][year] = percentile
    data = {
        "JIF": {},
        "JCI": {}
    }
    
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                metric = row.get("Metric Type")
                category = row.get("Category")
                year_str = row.get("Year")
                percentile_str = row.get("Percentile")
                
                if not metric or not category or not year_str or not percentile_str:
                    continue
                
                # Normalize metric to ensure it matches keys
                if metric not in data:
                    continue
                    
                # Parse Year
                try:
                    year = int(year_str)
                except ValueError:
                    continue # Skip invalid years (e.g. N/A)
                
                # Parse Percentile
                try:
                    percentile = float(percentile_str)
                except ValueError:
                    continue # Skip invalid percentiles (e.g. N/A)
                
                if category not in data[metric]:
                    data[metric][category] = {}
                
                data[metric][category][year] = percentile

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return {}
    except Exception as e:
        print(f"Error reading file: {e}")
        return {}

    # Calculate Data
    results = {
        "JIF": {},
        "JCI": {}
    }
    
    target_years = [start_year - i for i in range(5)] # [start, start-1, ..., start-4]
    
    for metric in ["JIF", "JCI"]:
        for category, years_data in data[metric].items():
            values = []
            for y in target_years:
                if y in years_data:
                    values.append(years_data[y])
            
            if values:
                avg = statistics.mean(values)
                results[metric][category] = round(avg, 2)
            else:
                # Decide what to do if no data in range. 
                # The user said "if some years are not available, ignore them".
                # If ALL are unavailable, it logically means no average.
                # We can either omit the category or set to None.
                # I'll omit it to keep it clean, or we can include it.
                # "return the average... for each category". 
                # I'll assume only categories with at least one data point in the range are relevant.
                pass
                
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python jcr_analysis.py <csv_file> <start_year>")
        sys.exit(1)
        
    fpath = sys.argv[1]
    try:
        s_year = int(sys.argv[2])
    except ValueError:
        print("Start year must be an integer")
        sys.exit(1)
        
    result = calculate_category_averages(fpath, s_year)
    import json
    print(json.dumps(result, indent=2))
