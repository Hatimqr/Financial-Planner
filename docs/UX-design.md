# Frontend UI Design Specification - MVP

## 1. Design Philosophy & Principles

The UI will be clean, minimal, and utilitarian. The primary goal is to present financial data with clarity and precision, enabling users to understand their financial state at a glance. The aesthetic will be professional and pleasant, avoiding unnecessary clutter and focusing on information hierarchy.

* **Clarity First:** Information must be unambiguous and easy to read.
* **Information Density:** Maximize useful information on screen without overwhelming the user.
* **Minimalism:** Every element should serve a purpose. Avoid decorative elements that don't aid in usability.
* **Responsiveness:** The design must be fully responsive and functional on desktop, tablet, and mobile devices.

## 2. Overall Layout & Navigation

The application will use a two-column layout: a persistent **Navigation Sidebar** on the left and a **Main Content Area** on the right.

### Navigation Sidebar

* **Appearance:** A fixed-width, dark-themed sidebar.
* **Content:**
  * **App Logo/Name:** At the top.
  * **Navigation Links:**
    * **Dashboard** (Icon: Home) - The default landing page.
    * **Accounts** (Icon: List) - The T-Account/Ledger view.
    * **Settings** (Icon: Gear)
  * **Global Add Button:** A prominent `+ New Transaction` button at the bottom of the sidebar, always accessible for quick data entry.

## 3. Dashboard View

The Dashboard is the central hub for visualizing the user's financial health.

### 3.1. Header & Global Filters

* **Location:** Top of the Main Content Area.
* **Components:**
  * **Date Range Filter:** A single, elegant date range picker component (e.g., "Last 30 Days", "This Year", "All Time", "Custom Range"). Defaults to "Year to Date".
  * **Account Filter:** A multi-select dropdown that allows users to check/uncheck which accounts are included in the dashboard charts and summaries. Defaults to "All Accounts".

### 3.2. Key Metric Display

* Below the filters, a prominent card displays the most critical number:
  * **Net Worth:** `Total Assets - Total Liabilities`. Displayed in a large font with a smaller label underneath. The color should change (e.g., green for positive, red for negative) to provide a quick visual cue.

### 3.3. Time-Series Chart

* **Primary Visualization:** A large, clean line chart that occupies the main portion of the dashboard.
* **Content:** It plots the balance of the selected accounts over the chosen date range. Each account will be a distinct colored line.
* **Interaction:**
  * Hovering over the chart will display a tooltip showing the exact values for each account at that specific date.
  * Clicking on a legend item will toggle the visibility of that account's line on the chart.

### 3.4. Account Summary Sections

* Below the chart, the dashboard will feature four collapsible sections, organized according to the accounting equation: **Assets, Liabilities, Income, and Expenses.**
* **Layout:** Each section is a card with a header.
  * **Header:** Shows the category name (e.g., "Assets") and the total balance for that category.
  * **Content:** A list of all accounts within that category. Each list item displays:
    * Account Name
    * Current Balance (right-aligned)
  * **Interaction:** Clicking on an account name in this list navigates the user directly to the **T-Account View** for that specific account.

## 4. T-Account / Ledger View

This view is for detailed transaction management and is the primary interface for data entry and editing.

### 4.1. View Header

* **Title:** Displays the name of the selected account (e.g., "Chase Checking").
* **Current Balance:** Shows the up-to-the-minute balance of the account.
* **Actions:** Buttons for `+ Add Transaction`, `Edit Account`, and `Delete Account`.

### 4.2. T-Account Layout

* The core of this view is a classic T-account table, which provides an intuitive ledger of all transactions.
* **Two Columns:**
  * **Debits (Left Side):** Transactions that increase the balance of Asset/Expense accounts or decrease the balance of Liability/Income/Equity accounts.
  * **Credits (Right Side):** Transactions that decrease the balance of Asset/Expense accounts or increase the balance of Liability/Income/Equity accounts.
* **Table Rows:** Each row within the Debit/Credit columns represents a single transaction "leg" and contains:
  * **Date**
  * **Description**
  * **Amount**
* **Interaction:** Clicking on any transaction row will open an "Edit Transaction" modal.

### 4.3. Add/Edit Transaction Modal

* A clean, focused modal form for creating or modifying transactions.
* **Fields:**
  * **Date:** (Defaults to today)
  * **Description:** (e.g., "Monthly Salary", "Groceries")
  * **Transaction Legs:** A dynamic list of inputs representing the debits and credits. Each leg has:
    * **Account:** A searchable dropdown of all accounts.
    * **Debit Amount:** Input field.
    * **Credit Amount:** Input field.
* **Validation:** The form will ensure that **Total Debits = Total Credits** before allowing the transaction to be saved, enforcing the double-entry rule.

## 5. Settings View

A simple, utilitarian page for managing the application's configuration.

### 5.1. Manage Accounts

* A table listing all created accounts.
* **Columns:** Account Name, Type, Current Balance.
* **Actions:** Each row has "Edit" and "Delete" buttons.
* **Add Account:** A button above the table to open a modal for creating a new account (Name and Type).

### 5.2. Global Variables

* A read-only section for displaying system information for debugging or reference.
* **Content:**
  * Database Path
  * API Version
  * Last Backup Time (Future Feature)
