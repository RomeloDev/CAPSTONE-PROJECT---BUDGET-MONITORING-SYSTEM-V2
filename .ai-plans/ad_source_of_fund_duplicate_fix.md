# AD Source of Fund Duplicate Bug — Implementation Plan

## Bug Summary
A critical vulnerability exists in the Activity Design (AD) creation form where users can select the same budget line item multiple times, allowing them to bypass budget limits and create duplicate allocations. This breaks the budget integrity because the system will deduct funds multiple times or allow allocations exceeding the actual available balance, leading to negative remaining balances.

## Root Cause Analysis
The issue stems from a combination of frontend and backend flaws (Root Cause E):
1. **Frontend Dropdown Fails to Clear (UI Bug)**: The `updateChoices()` JavaScript function rebuilds the dropdown choices but fails to include an empty placeholder option (`value: ''`). Because of this, the subsequent call to `choices.setChoiceByValue('')` fails silently. The just-added line item remains actively selected in the DOM, allowing the user to click "Add" again immediately.
2. **Backend Missing Duplicate Check in Session**: The `add_draft_allocation` AJAX endpoint in `apps/end_user_panel/views.py` blindly appends new allocations to `request.session['ad_draft_allocations']` without checking if the `full_value` (line item + quarter combination) is already present.
3. **Backend Missing Final Amount Validation**: During the `submit_final` action, the backend blindly creates `ActivityDesignAllocation` records without verifying if the `amount` exceeds the `get_quarter_available()` of the line item.

The bug originates in:
- `apps/end_user_panel/templates/end_user_panel/activity_design_upload.html` (lines ~333-350 for `updateChoices`)
- `apps/end_user_panel/views.py` (lines ~1790 for session append, and lines ~1870 for final submit)

## Files That Need Changes
1. `apps/end_user_panel/templates/end_user_panel/activity_design_upload.html` - Fix `updateChoices()` to include a placeholder and ensure the active item is cleared.
2. `apps/end_user_panel/views.py` - Add validation to `add_draft_allocation` to prevent duplicates, and to `submit_final` to enforce budget limits securely.

## Proposed Fix

### Frontend Changes (if any)
- Modify `updateChoices()` to explicitly push an empty placeholder object to `choicesData` before adding the available line items:
  ```javascript
  choicesData.push({ value: '', label: 'Search funding source...', placeholder: true });
  ```
- Before calling `choices.setChoices(...)`, call `choices.removeActiveItems();` to clear any lingering selection state.
- Keep the `!allocatedKeys.has(key)` filter, which will now work correctly since the UI will actually reset.

### Backend Changes (if any)
- **Session Duplicate Prevention**: In `apps/end_user_panel/views.py` under `action == 'add_draft_allocation'`, check if `full_value` already exists in the `allocations` list before appending. Return an error if it does.
- **Session Amount Validation**: Also in `add_draft_allocation`, verify that the requested `amount` does not exceed the line item's available balance (`item.get_quarter_available(quarter)`).

### Validation Layer
- **Final Submit Validation**: In the `submit_final` action block, before creating the `ActivityDesignAllocation` records in the database, loop through `items_data` and assert that the total requested amount for each line item does not exceed `line_item.get_quarter_available(item['quarter'])`. If it does, abort the transaction and return a form error.

## Risk Assessment
- **What could break**: If the validation logic is flawed, valid AD submissions might be incorrectly rejected. The `get_quarter_available()` must correctly account for the AD's own draft if applicable (though currently drafts don't deduct).
- **Existing AD records**: Existing AD records with duplicate allocations are already in the database. This fix prevents new ones from being created. Fixing historical data would require a separate data migration script, which is outside the immediate scope of this UI/validation fix.
- **Migrations**: No schema changes are required, so no migrations are needed.

## Verification Plan
1. **Frontend Test**: Open the AD upload page, select a line item, enter an amount, and click "Add". Verify that the dropdown resets to "Search funding source..." and the added item is no longer in the list.
2. **Duplicate Prevention Test**: Try to manipulate the DOM to submit the same line item again. Verify the backend AJAX endpoint rejects it with an error.
3. **Budget Limit Test**: Try to add an amount greater than the available balance. Verify the backend rejects it.
4. **Final Submit Test**: Submit the AD and verify the `ActivityDesignAllocation` records are created correctly and the remaining budget is correctly reserved.
5. **Existing Records**: View an existing AD detail page to ensure it still renders correctly.

## Execution Order
1. [x] Implement Frontend fixes in `apps/end_user_panel/templates/end_user_panel/activity_design_upload.html`.
2. [x] Implement Backend Validation in `apps/end_user_panel/views.py` (`add_draft_allocation` and `submit_final`).
3. [x] Test the complete flow.
