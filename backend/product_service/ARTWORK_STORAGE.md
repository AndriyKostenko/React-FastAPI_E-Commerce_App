# Generated artwork storage

Generated T-shirt artwork is normalized to transparency-capable RGBA PNG, measured, and
validated before it is persisted. The browser receives a preview URL plus a
signed immutable manifest. Orders verify that manifest and store its S3 object
key, SHA-256 digest, pixel dimensions, physical print area, and effective DPI.
The preview URL is never the production identifier.

## Production configuration

Configure both `product-service` and `product-taskiq-worker` with:

```dotenv
ARTWORK_STORAGE_BACKEND=s3
AWS_S3_ARTWORK_BUCKET=your-private-artwork-bucket
AWS_S3_REGION=ca-central-1
PRINT_IMAGE_GENERATION_SIZE=4K
ARTWORK_SIGNING_SECRET=a-long-random-secret-shared-with-order-service
```

Optional settings:

```dotenv
# CloudFront URL backed by private S3 through Origin Access Control. When this
# is absent, the API returns a short-lived S3 GET URL for previewing.
AWS_S3_PUBLIC_BASE_URL=https://artwork.example.com

# Enables SSE-KMS instead of the default explicit SSE-S3 request.
AWS_S3_KMS_KEY_ID=arn:aws:kms:ca-central-1:123456789012:key/...

# Useful for LocalStack or another S3-compatible development endpoint only.
AWS_S3_ENDPOINT_URL=http://localstack:4566
```

Do not configure long-lived AWS access keys in application environment files.
Attach a workload role to the container/task/instance. Its least-privilege
policy needs `s3:PutObject` and `s3:GetObject` only for
`arn:aws:s3:::your-private-artwork-bucket/generated-designs/*`. Add the
corresponding KMS encrypt/decrypt permissions only when SSE-KMS is enabled.

Keep all S3 Block Public Access controls enabled, disable ACLs with
bucket-owner-enforced object ownership, require TLS, and enable bucket
versioning. Do not apply an expiry rule to ordered artwork; an operational
cleanup job may separately remove unreferenced generation drafts after a safe
retention period.

The default maximum garment area is 15 x 18 inches. Assets must contain at
least 2250 x 2700 pixels (150 effective DPI at that size); the generator asks
for native 4K output and the service deliberately does not upscale small
images. PNG files are tagged at 300 DPI for printer software, while order-time
effective DPI is calculated from actual pixels and the selected placement.
