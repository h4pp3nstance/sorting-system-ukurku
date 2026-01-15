# Test Images for Dimension Detection

## Folder Structure

- `top/` - Images from top camera (untuk mengukur panjang × lebar)
- `side/` - Images from side camera (untuk mengukur tinggi)

## Image Requirements

### For Top Camera (`top/`)
- Tampak atas paket (top-down view)
- Background kontras dengan paket
- Pencahayaan merata
- Include calibration reference (ruler/known size object)
- Format: JPG/PNG
- Naming: `package_top_001.jpg`, `package_top_002.jpg`, etc.

### For Side Camera (`side/`)
- Tampak samping paket
- Background kontras
- Paket harus terlihat utuh dari samping
- Format: JPG/PNG
- Naming: `package_side_001.jpg`, `package_side_002.jpg`, etc.

## How to Add Test Images

1. Take photos of packages with known dimensions
2. Record actual dimensions for validation
3. Name files consistently
4. Place in appropriate folder

## Sample Dimensions for Testing

| Package | P (cm) | L (cm) | T (cm) | Expected Vol. Weight (g) |
|---------|--------|--------|--------|--------------------------|
| Small   | 10     | 8      | 6      | 80                       |
| Medium  | 15     | 12     | 10     | 300                      |
| Large   | 20     | 18     | 15     | 900                      |
| Max     | 23     | 23     | 23     | 2028                     |
