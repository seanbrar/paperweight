# paperweight roadmap

This document outlines the planned features and improvements for the paperweight project. Please note that this roadmap is subject to change based on user feedback and project priorities.

## Short-term Goals

### General Improvements
- [ ] Implement general code cleanup and optimization
- [ ] Increase overall speed through asynchronous operations
- [ ] Create a web-hosted demo of the program

### Scraper Module
- [ ] Build and implement PDF extraction evaluations
- [ ] Add retry logic in API/scraper (possibly using tenacity)
- [ ] Revisit and improve date checking logic
  - [ ] Develop comprehensive testing suite with dummy papers
- [ ] Parse out unnecessary content (e.g., references, LaTeX preambles)
- [ ] Add support for extracting and handling images from papers

### Processor Module
- [ ] Refine and expand the normalization score system for papers

### Analyzer Module
- [ ] Conduct additional testing of LLM integration
- [ ] Implement rate limits for API calls
- [ ] Explore and potentially add support for a wider selection of models
- [ ] Refine and optimize summarization prompts

### Notifier Module
- [ ] Improve handling of scenarios where all papers are discarded
- [ ] Revisit and potentially expand the fields included in notifications (e.g., authors)
- [ ] Add more options for paper ordering and field selection in email notifications

## Medium-term Goals

- [ ] Replace current static keyword-based filtering with a machine learning recommendation engine
  - [ ] Ensure interface compatibility is maintained
- [ ] Expand notification methods beyond email
  - [ ] Investigate possibilities like desktop notifications or a desktop agent
- [ ] Rethink the notification system to make SMTP configuration less cumbersome for users

## Long-term Goals

- [ ] Add support for additional academic paper sources beyond arXiv
- [ ] Implement machine learning-based paper recommendations
- [ ] Continuously improve and refine the LLM-based summarization feature

## Ongoing Tasks

- [ ] Maintain and update documentation
- [ ] Address bugs and issues reported by users
- [ ] Optimize performance and resource usage

We welcome contributions and suggestions from the community. If you have ideas for new features or improvements, please open an issue on the [GitHub repository](https://github.com/seanbrar/paperweight/issues).

For information on how to contribute to paperweight, please see the [contributing guide](docs/CONTRIBUTING.md).