
import unittest
from jcr_analysis import calculate_category_averages

class TestJCRAnalysis(unittest.TestCase):
    def test_bioethics_2024(self):
        file_path = "BIOETHICS_jcr_data.csv"
        start_year = 2024
        
        results = calculate_category_averages(file_path, start_year)
        
        print("Results:", results)
        
        # JIF - ETHICS
        # 2024: 73.4, 2023: 64.3, 2022: 74.6, 2021: 74.11, 2020: 58.04
        # Avg: 68.89
        self.assertIn("JIF", results)
        self.assertIn("ETHICS", results["JIF"])
        self.assertAlmostEqual(results["JIF"]["ETHICS"], 68.89, places=2)
        
        # JIF - MEDICAL ETHICS
        # 2024: 63.0, 2023: 58.7, 2022: 53.1, 2021: 53.13, 2020: 40.63
        # Avg: 53.71
        self.assertIn("MEDICAL ETHICS", results["JIF"])
        self.assertAlmostEqual(results["JIF"]["MEDICAL ETHICS"], 53.71, places=2)

if __name__ == "__main__":
    unittest.main()
