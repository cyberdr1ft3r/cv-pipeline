# CV Templates

This folder contains HTML templates for CV generation.

## Available Templates

### 1. Classic (default)
- Traditional two-column layout
- Blue color scheme (#2c3e50, #3498db)
- Professional and clean design
- Best for: Corporate jobs, traditional industries

### 2. Modern
- Gradient header (purple/violet)
- Modern typography
- Skill tags with rounded corners
- Best for: Tech companies, startups, creative roles

### 3. Minimal
- Black and white design
- Clean typography with Helvetica Neue
- Minimalist aesthetic
- Best for: Design roles, executive positions, modern companies

## Configuration

To select a template, edit `config/config_yaml.yaml`:

```yaml
cv_generation:
  template: "classic"  # Options: "classic", "modern", "minimal"
```

## Watermark

Watermarks are automatically added based on your configuration:

1. **Enable/Disable**: Set `cv_generation.watermark.enabled: true/false`
2. **Custom Text**: Set `cv_generation.watermark.text: "YOUR TEXT"`
3. **Company Name**: If text is empty, uses `company.name` from config

Example:
```yaml
cv_generation:
  watermark:
    enabled: true
    text: "CONFIDENTIAL"

company:
  name: "TechCorp Inc."
```

## Creating Custom Templates

You can create your own templates:

1. Create a new HTML file in this folder (e.g., `my_template.html`)
2. Use the following placeholders:
   - `{nom_complet}` - Candidate name
   - `{titre}` - Candidate title/profile
   - `{left_content}` - Left column content (education, skills, languages)
   - `{right_content_page1}` - Right column content (experience, projects)
   - `{watermark}` - Company watermark text

3. Add to `config/config_yaml.yaml`:
   ```yaml
   cv_generation:
     template: "my_template"
   ```

## Template Structure

All templates must follow this structure:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>CV - {nom_complet}</title>
    <style>
        /* Your CSS styles */
        .watermark {
            /* Watermark styling - required */
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-45deg);
            font-size: 48pt;
            color: rgba(52, 152, 219, 0.1);
            font-weight: bold;
            pointer-events: none;
            z-index: 0;
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="watermark">{watermark}</div>
        <!-- Your template structure -->
        <div class="header">
            <div class="name">{nom_complet}</div>
            <div class="profile">{titre}</div>
        </div>
        <div class="content">
            <div class="left-column">{left_content}</div>
            <div class="right-column">{right_content_page1}</div>
        </div>
    </div>
</body>
</html>
```

## Tips

- **A4 Format**: All templates should be designed for A4 (21cm × 29.7cm)
- **Watermark**: The watermark should be positioned absolutely with low opacity
- **Z-index**: Keep watermark at z-index: 0 and content at z-index: 1
- **Fonts**: Use web-safe fonts or embed fonts if needed
- **Colors**: Match your company branding
- **Responsive**: Templates should handle multi-page content automatically

## Examples

### Corporate Template
```css
.header {
    background: #1a365d;
    color: white;
}
h1 {
    border-bottom: 2px solid #2c5282;
}
```

### Creative Template
```css
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}
h1 {
    border-bottom: 3px solid #f093fb;
}
```

### Minimal Template
```css
.header {
    border-bottom: 4px solid #000;
    color: #000;
}
h1 {
    border-bottom: 1px solid #ddd;
    font-weight: 300;
}
```

## Support

For questions or issues, please refer to the main project documentation.