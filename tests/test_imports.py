def test_package_imports_and_version():
    import wealth_analyzer
    import wealth_analyzer.analysis.dca
    import wealth_analyzer.analysis.lump_sum
    import wealth_analyzer.analysis.metrics
    import wealth_analyzer.cli
    import wealth_analyzer.config
    import wealth_analyzer.data.cache
    import wealth_analyzer.data.fetcher
    import wealth_analyzer.reports.excel_report
    import wealth_analyzer.reports.pdf_report

    assert wealth_analyzer.__version__ == "1.0.0"

