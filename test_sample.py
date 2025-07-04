#!/usr/bin/env python3
"""
Sample Python file for testing Halos code analysis.
This file demonstrates various code constructs for parsing.
"""

import os
import sys
from typing import List, Dict, Any

class DataProcessor:
    """A sample class for data processing operations."""
    
    def __init__(self, name: str):
        """Initialize the data processor with a name."""
        self.name = name
        self.data = []
    
    def add_data(self, item: Any) -> None:
        """Add an item to the data collection."""
        self.data.append(item)
        print(f"Added {item} to {self.name}")
    
    def process_data(self) -> List[Any]:
        """Process all data items and return results."""
        results = []
        for item in self.data:
            if isinstance(item, str):
                results.append(item.upper())
            elif isinstance(item, (int, float)):
                results.append(item * 2)
            else:
                results.append(str(item))
        return results

def main():
    """Main function to demonstrate the data processor."""
    processor = DataProcessor("test_processor")
    
    # Add some sample data
    processor.add_data("hello")
    processor.add_data(42)
    processor.add_data(3.14)
    
    # Process the data
    results = processor.process_data()
    print(f"Processed results: {results}")

if __name__ == "__main__":
    main() 