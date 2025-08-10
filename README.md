
# DbRheoCLI - Database/Data Analysis Agent

![DbRheo CLI Interface](https://github.com/Din829/DbRheo-CLI/blob/master/docs/images/dbrheo-cli-interface.png)

DbRheo is a database operations and data analysis CLI agent that provides natural language database query execution, schema exploration, risk assessment capabilities, and Python-powered data analysis features.


## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI

# 2. Install dependencies
pip install -r requirements.txt


# 3. Environment setup
cp .env.example .env
# Set either GOOGLE_API_KEY or OPENAI_API_KEY in the .env file
# No need to modify other contents in .env.example
# Claude models are not recommended at this time as PromptCaching is not yet applied


# 4. Launch CLI
cd packages/cli
python cli.py
```

## Key Features

### Core Capabilities
- **Natural Language Query Processing**: Database operation instructions in natural language
- **Intelligent SQL Generation**: Automatic generation of safe and optimized queries
- **Automatic Schema Discovery**: Dynamic analysis of database structures
- **Risk Assessment System**: Pre-detection and warnings for dangerous operations
- **Python Code Execution**: Data analysis, visualization, and automation script execution
- **Data Export**: Result output in CSV, JSON, and Excel formats

### Technical Features
- **Asynchronous Processing**: High-performance async/await implementation
- **Multi-Database Support**: PostgreSQL, MySQL, SQLite compatibility
- **Modular Design**: Extensible plugin architecture
- **Comprehensive Logging**: Detailed operation history and debug information
- **Intelligent Input**: Automatic multi-line detection and paste processing
- **Streaming Output**: Real-time response display
- **Internationalization**: Multi-language support (Japanese, English)

## System Requirements

### Required Environment
- Python 3.9 or higher
- Node.js 20 or higher (only for Web UI development)

### Supported Databases
Currently supports 3 main database types (more can be added via adapter interface):
- **PostgreSQL** 12+ (via asyncpg driver)
- **MySQL/MariaDB** 8.0+ (via aiomysql driver)
- **SQLite** 3.35+ (via aiosqlite driver)

*Note: Additional database types can be easily integrated through the adapter factory pattern. The system supports dynamic adapter registration and automatic driver detection.*

## Installation Guide

### 1. Clone the Repository
```bash
git clone https://github.com/Din829/DbRheo-CLI.git
cd DbRheo-CLI
```

Alternative:
https://dev.azure.com/HPSMDI/POC_Agent/_git/db-rheo-cli


### 2. Python Environment Setup
```bash

# Install dependencies
pip install -r requirements.txt

```

### 3. Package Installation (Optional)
```bash
# Install core package
cd packages/core
pip install -e .
cd ../..

# Install CLI package
cd packages/cli
pip install -e .
cd ../..

# Verify installation
pip show dbrheo-core dbrheo-cli
```

**Note**: You can run directly in development mode without installing packages.

### 4. Environment Configuration
```bash
# Copy configuration file
cp .env.example .env

# Edit the .env file and configure:
# - Google API key
# - Database connection information
```

### 5. Test Data
The `testdata/` directory contains sample datasets for testing the agent:
- **adult.data**: Adult Census Income dataset for data analysis testing
- **adult.names**: Dataset description and column information
- **adult.test**: Test dataset for validation
- Additional sample files for various testing scenarios

You can use these datasets to test DbRheo's data analysis capabilities and SQL generation features.

## Launch Methods

### CLI Mode Launch

#### After Package Installation

```bash
# Display help
/help

# Specify model
/model
```




## Usage Examples

### Basic Conversation Examples
```
DbRheo> Tell me about the structure of the users table
[Executing schema exploration...]
Structure of table 'users':
- id: INTEGER (Primary Key)
- name: VARCHAR(100)
- email: VARCHAR(255)
- created_at: TIMESTAMP

DbRheo> Show me the latest 10 users
[Generating SQL query...]
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;
[Displaying execution results...]
```

### Data Analysis Features
```
DbRheo> Analyze and visualize sales data using Python
[Generating Python code...]
import pandas as pd
import matplotlib.pyplot as plt

# Retrieve sales data from database
df = pd.read_sql("SELECT * FROM sales", connection)

# Monthly sales aggregation
monthly_sales = df.groupby('month')['amount'].sum()

# Create graph
plt.figure(figsize=(10, 6))
monthly_sales.plot(kind='bar')
plt.title('Monthly Sales Trends')
plt.savefig('sales_analysis.png')

[Execution result: Generated graph file sales_analysis.png]
```

### Advanced SQL Features
```
DbRheo> Create monthly aggregation of sales data
[Generating complex query...]
SELECT
    DATE_TRUNC('month', order_date) as month,
    SUM(amount) as total_sales
FROM orders
GROUP BY month
ORDER BY month;
```

### Testing with Sample Data
```
DbRheo> Load the adult dataset from testdata and analyze income distribution
[Loading data from testdata/adult.data...]
[Generating analysis code...]
import pandas as pd

# Load the adult census dataset
df = pd.read_csv('testdata/adult.data', header=None)
# Apply column names from adult.names
df.columns = ['age', 'workclass', 'fnlwgt', 'education', ...]

# Analyze income distribution
income_dist = df['income'].value_counts()
print("Income Distribution:")
print(income_dist)

[Execution result: Income analysis completed]
```



