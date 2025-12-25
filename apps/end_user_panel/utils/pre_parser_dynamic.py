"""
Dynamic PRE Excel Parser
Extracts ALL line items including custom ones added by users
"""
from openpyxl import load_workbook
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Optional
import logging
# Configure logging
logger = logging.getLogger(__name__)
class DynamicPREParser:
    """
    Dynamic parser that extracts all line items from PRE Excel file
    including custom items added by end users
    """
    # Section boundaries in the PRE template (Rows are 1-indexed)
    SECTION_BOUNDARIES = {
        'receipts': {
            'start_row': 9,
            'end_row': 11,
            'category': 'RECEIPTS',
            'subcategory': 'Budget Receipts',
            'has_subcategories': False,
        },
        'personnel': {
            'start_row': 13,
            'end_row': 19,
            'category': 'PERSONNEL',
            'subcategory': 'Personnel Services',
            'has_subcategories': False,
        },
        'mooe': {
            'start_row': 20,
            'end_row': 132,
            'category': 'MOOE',
            'subcategory': None,  # Will be detected dynamically
            'has_subcategories': True,
        },
        'capital': {
            'start_row': 133,
            'end_row': 176,
            'category': 'CAPITAL',
            'subcategory': None,  # Will be detected dynamically
            'has_subcategories': True,
        },
    }
    # Grand total row
    GRAND_TOTAL_ROW = 177
    # Row patterns to skip (section headers, totals, etc.)
    SKIP_PATTERNS = [
        'TOTAL', 'Total', 'Sub-total', 'RECEIPTS / BUDGET', 'BUDGET BY OBJECT',
        'Personnel Services', 'Maintenance and Other Operating', 'MAINTENANCE AND OTHER',
        'CAPITAL OUTLAYS', 'Current Operating',
    ]
    # Standard template items (for custom item detection)
    STANDARD_ITEMS = {
        'GASS - TUITION FEE', 'Basic Salary', 'Honoraria', 'Overtime Pay',
        'Travelling expenses-local', 'Travelling Expenses-foreign', 'Training Expenses',
        'Office Supplies Expenses', 'Accountable Form Expenses',
        'Agricultural and Marine Supplies expenses', 'Drugs and Medicines',
        # ... (This list can be expanded)
    }
    def __init__(self, file_obj):
        self.file_obj = file_obj
        self.workbook = None
        self.worksheet = None
        self.errors = []
        self.warnings = []
        self.validation_summary = {
            'cell_errors': [],
            'row_total_mismatches': [],
            'grand_total_error': None,
        }
    def validate_template(self) -> bool:
        try:
            self.workbook = load_workbook(self.file_obj, data_only=True)
            self.worksheet = self.workbook.active
            if not self.worksheet:
                self.errors.append("Could not read Excel worksheet")
                return False
            
            # Check for Grand Total row
            grand_total_cell = self.worksheet[f'A{self.GRAND_TOTAL_ROW}'].value
            if not grand_total_cell or 'TOTAL' not in str(grand_total_cell).upper():
                self.warnings.append(f"Warning: Grand total row expected at row {self.GRAND_TOTAL_ROW}")
            
            return True
        except Exception as e:
            self.errors.append(f"Error reading Excel file: {str(e)}")
            return False
    def _parse_cell_value(self, cell_value) -> Decimal:
        try:
            if cell_value is None or cell_value == '':
                return Decimal('0')
            value_str = str(cell_value).strip().upper()
            if value_str in ['XXX', 'X', 'XX', 'XXXX', '-', '']:
                return Decimal('0')
            return Decimal(str(cell_value))
        except (InvalidOperation, ValueError, TypeError):
            self.warnings.append(f"Invalid cell value: '{cell_value}' - treated as 0")
            return Decimal('0')
    def _is_skip_row(self, item_name: str) -> bool:
        if not item_name: return True
        item_name_upper = str(item_name).strip().upper()
        for pattern in self.SKIP_PATTERNS:
            if pattern.upper() in item_name_upper:
                return True
        return False
    def _detect_subcategory(self, row_num: int, section_key: str) -> Optional[str]:
        section = self.SECTION_BOUNDARIES[section_key]
        if not section['has_subcategories']:
            return section['subcategory']
        
        # Scan backwards for header
        for check_row in range(row_num - 1, section['start_row'] - 1, -1):
            check_name = self.worksheet[f'A{check_row}'].value
            if not check_name: continue
            check_q1 = self.worksheet[f'E{check_row}'].value
            # Header has name but no values
            if check_name and not check_q1:
                if not self._is_skip_row(check_name):
                    return str(check_name).strip()
        return 'Uncategorized'
    def _validate_row_total(self, row_num, item_name, q1, q2, q3, q4):
        calculated = q1 + q2 + q3 + q4
        excel_total = self._parse_cell_value(self.worksheet[f'I{row_num}'].value)
        if abs(calculated - excel_total) > Decimal('0.01'):
            return {
                'row': row_num, 'item': item_name,
                'calculated': float(calculated), 'excel_total': float(excel_total),
                'difference': float(abs(calculated - excel_total))
            }
        return None
    def extract_line_items_dynamic(self) -> Dict:
        if not self.worksheet: return None
        
        extracted_data = {'receipts': [], 'personnel': [], 'mooe': [], 'capital': []}
        total_items = 0
        custom_items_count = 0
        for section_key, section_info in self.SECTION_BOUNDARIES.items():
            start, end = section_info['start_row'], section_info['end_row']
            
            for row_num in range(start, end + 1):
                # Check Columns A, B, C for item name
                item_name = (
                    self.worksheet[f'A{row_num}'].value or
                    self.worksheet[f'B{row_num}'].value or
                    self.worksheet[f'C{row_num}'].value
                )
                
                if not item_name or self._is_skip_row(item_name):
                    continue
                
                item_name = str(item_name).strip()
                
                q1 = self._parse_cell_value(self.worksheet[f'E{row_num}'].value)
                q2 = self._parse_cell_value(self.worksheet[f'F{row_num}'].value)
                q3 = self._parse_cell_value(self.worksheet[f'G{row_num}'].value)
                q4 = self._parse_cell_value(self.worksheet[f'H{row_num}'].value)
                
                if q1 == 0 and q2 == 0 and q3 == 0 and q4 == 0:
                    continue
                mismatch = self._validate_row_total(row_num, item_name, q1, q2, q3, q4)
                if mismatch:
                    self.validation_summary['row_total_mismatches'].append(mismatch)
                    self.warnings.append(f"Row {row_num} ({item_name}): Formula error corrected.")
                subcategory = self._detect_subcategory(row_num, section_key)
                is_custom = item_name not in self.STANDARD_ITEMS
                if is_custom: custom_items_count += 1
                
                item_data = {
                    'row_number': row_num,
                    'item_name': item_name,
                    'q1': float(q1), 'q2': float(q2), 'q3': float(q3), 'q4': float(q4),
                    'total': float(q1 + q2 + q3 + q4),
                    'category': section_info['category'],
                    'subcategory': subcategory,
                    'is_custom_item': is_custom,
                }
                
                extracted_data[section_key].append(item_data)
                total_items += 1
                
        extracted_data['_metadata'] = {
            'total_items': total_items,
            'custom_items_count': custom_items_count,
        }
        return extracted_data
    def calculate_grand_total(self, extracted_data):
        total = Decimal('0')
        for key in ['receipts', 'personnel', 'mooe', 'capital']:
            for item in extracted_data.get(key, []):
                total += Decimal(str(item['total']))
        return total
    def get_fiscal_year(self):
        try:
            val = self.worksheet['A3'].value
            return str(val).replace('FY', '').strip() if val else None
        except: return None
    def parse(self):
        if not self.validate_template():
            return {'success': False, 'errors': self.errors}
            
        extracted_data = self.extract_line_items_dynamic()
        grand_total = self.calculate_grand_total(extracted_data)
        fiscal_year = self.get_fiscal_year()
        
        metadata = extracted_data.pop('_metadata', {})
        
        return {
            'success': True,
            'data': extracted_data,
            'grand_total': float(grand_total),
            'fiscal_year': fiscal_year,
            'total_items': metadata.get('total_items', 0),
            'errors': self.errors,
            'warnings': self.warnings + [f"Formula mismatch: {m['item']}" for m in self.validation_summary['row_total_mismatches']],
            'validation_summary': self.validation_summary
        }
def parse_pre_excel_dynamic(file_obj) -> Dict:
    parser = DynamicPREParser(file_obj)
    return parser.parse()