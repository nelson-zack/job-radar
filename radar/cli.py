# radar/cli.py
def main() -> None:
    """
    Thin entry point so we can expose a console_script later:
      job-radar = radar.cli:main
    Delegates to the existing root script while we migrate logic into the package.
    """
    import job_radar  # imports the root script module
    job_radar.main()

if __name__ == "__main__":
    # When executed as `python -m radar.cli ...`
    main()