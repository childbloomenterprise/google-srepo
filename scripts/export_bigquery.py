"""Production export placeholder.

The prototype dashboard reads from CaseStore. A production BigQuery export should be designed
with a data-retention policy and explicit consent before writing policyholder data.
"""


def main() -> None:
    print("BigQuery export is not configured for the prototype.")


if __name__ == "__main__":
    main()
