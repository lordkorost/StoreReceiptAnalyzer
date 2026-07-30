# Contributing

Contributions are welcome.

If you would like to improve StoreReceiptAnalyzer:

1. Fork the repository.
2. Create a feature branch.

```bash
git checkout -b feature/my-feature
```

3. Commit your changes.

```bash
git commit -m "feat: add my feature"
```

4. Push your branch.

```bash
git push origin feature/my-feature
```

5. Open a Pull Request.

## Areas where contributions are especially appreciated

### OCR Normalizer

Improve the receipt normalization engine to better handle:

- product descriptions
- quantities
- discounts
- prices
- different receipt layouts

The goal is to make the parser flexible enough to support receipts from many countries.

### Store Templates

Create and improve default templates for supermarkets and retailers outside Italy.

### Internationalization

Improve existing translations or add support for new languages.

### AI Improvements

Experiment with:

- better extraction prompts
- improved categorization prompts
- alternative Ollama models
- better default model configurations

### Error Handling

Improve recovery workflows when:

- OCR fails
- parsing is incomplete
- AI extraction produces unexpected results

Please open an Issue before starting major changes so the implementation can be discussed first.
