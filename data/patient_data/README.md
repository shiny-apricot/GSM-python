# Patient Data Directory

Place patient expression CSV files here for clinical inference.

## Expected Format

- **Rows**: Patient samples (one per row)
- **Columns**: Gene identifiers (must match the training data gene names)
- **Optional**: A `sample_id` column for labeling patients
- **No class/label column needed** (the model predicts this)

## Example

```csv
sample_id,TP53,BRCA1,EGFR,MYC,KRAS
patient_001,5.23,3.41,7.89,2.15,4.67
patient_002,3.12,6.78,4.56,8.90,1.23
patient_003,7.45,2.34,5.67,3.45,6.78
```

## Usage

```bash
# Interactive mode auto-discovers files from this folder
python run_gsm.py

# Or specify directly
python run_gsm.py infer -b output/.../bundles/bundle.gsm.zip -p data/patient_data/my_patients.csv
```
