# Data Dictionary: uae_infrastructure_projects

**Source File:** `uae_infrastructure_projects.csv`  
**Total Records:** 500  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `project_id` | str | 0.0% | 500 | Project Id field | INFRA-0001, INFRA-0002 |
| `project_name` | str | 0.0% | 200 | Project Name field | Smart City - Zone 18, Cycling Track - Zone 9 |
| `project_type` | str | 0.0% | 12 | Project Type field | Smart City, Cycling Track |
| `authority` | str | 0.0% | 9 | Authority field | Smart Dubai, ADJP |
| `emirate` | str | 0.0% | 4 | Emirate field | Dubai, Sharjah |
| `budget_aed_million` | int64 | 0.0% | 475 | Budget Aed Million field | min:58.0, max:4995.0 |
| `start_year` | int64 | 0.0% | 7 | Start Year field | min:2018.0, max:2024.0 |
| `expected_completion_year` | int64 | 0.0% | 11 | Expected Completion Year field | min:2019.0, max:2029.0 |
| `status` | str | 0.0% | 4 | Status field | Completed, In Progress |
| `latitude` | float64 | 0.0% | 477 | Geographical latitude coordinate | min:24.8, max:25.4 |
| `longitude` | float64 | 0.0% | 481 | Geographical longitude coordinate | min:54.9, max:55.7 |
| `impact_on_real_estate` | str | 0.0% | 3 | Impact On Real Estate field | Medium, Medium |
| `estimated_jobs_created` | int64 | 0.0% | 490 | Estimated Jobs Created field | min:133.0, max:9996.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.