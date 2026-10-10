# Generated artwork storage

Generated T-shirt artwork is normalized to transparency-capable RGBA PNG, measured, and
validated before it is persisted. The browser receives a preview URL plus a
signed immutable manifest. Orders verify that manifest and store its S3 object
key, SHA-256 digest, pixel dimensions, physical print area, and effective DPI.
The preview URL is never the production identifier.

## Production configuration

All image storage goes through `storage/` (`ObjectStorageProvider`): two
buckets, never mixed.

| Bucket | Holds | Access |
| --- | --- | --- |
| catalogue (`AWS_S3_CATALOGUE_BUCKET`) | CJ product/variant images copied at sync (`catalogue/cj/`), admin uploads and category icons (`catalogue/uploads/`) | public read, served from `AWS_S3_CATALOGUE_PUBLIC_BASE_URL` |
| private (`AWS_S3_PRIVATE_BUCKET`) | generated designs (`generated-designs/`), return photos (`return-evidence/`, order-service) | presigned GETs only |

Configure product-service, its consumer, taskiq worker and scheduler, and
order-service with:

```dotenv
OBJECT_STORAGE_BACKEND=s3
AWS_S3_CATALOGUE_BUCKET=your-public-catalogue-bucket
AWS_S3_CATALOGUE_PUBLIC_BASE_URL=https://images.example.com
AWS_S3_PRIVATE_BUCKET=your-private-bucket
AWS_S3_REGION=ca-central-1
PRINT_IMAGE_GENERATION_SIZE=4K
ARTWORK_SIGNING_SECRET=a-long-random-secret-shared-with-order-service
```

`ARTWORK_STORAGE_BACKEND` and `AWS_S3_ARTWORK_BUCKET` are still read as the
old names of `OBJECT_STORAGE_BACKEND` and `AWS_S3_PRIVATE_BUCKET`.

The database stores catalogue *keys*; responses add
`AWS_S3_CATALOGUE_PUBLIC_BASE_URL` (`storage/catalogue_url.py`), so moving the
bucket behind another CDN is a settings change. The frontend's `next.config.js`
allows that host through `CATALOGUE_IMAGE_HOST`.

Optional settings:

```dotenv
# CloudFront in front of the *private* bucket for design previews, through
# Origin Access Control. Without it, previews are short-lived presigned GETs.
AWS_S3_PUBLIC_BASE_URL=https://artwork.example.com

# Enables SSE-KMS instead of the default explicit SSE-S3 request.
AWS_S3_KMS_KEY_ID=arn:aws:kms:ca-central-1:123456789012:key/...

# An S3-compatible server instead of AWS (locally: SeaweedFS, set by dev.sh).
AWS_S3_ENDPOINT_URL=http://127.0.0.1:8333
```

**Credentials.** In AWS, attach a workload role to each container/task; the
default credential chain finds it and `AWS_S3_ACCESS_KEY_ID` /
`AWS_S3_SECRET_ACCESS_KEY` stay unset. Those two exist for S3-compatible
servers only and are Vault secrets, one pair per service. Least privilege:

- product-service: `s3:PutObject`, `s3:GetObject` on
  `arn:aws:s3:::<catalogue>/catalogue/*` and
  `arn:aws:s3:::<private>/generated-designs/*`
- order-service: `s3:PutObject`, `s3:GetObject` on
  `arn:aws:s3:::<private>/return-evidence/*`
- add the KMS encrypt/decrypt permissions only when SSE-KMS is enabled.

**Buckets.** Private bucket: keep all Block Public Access controls on.
Catalogue bucket: public read of `catalogue/*` only (a bucket policy, or
better CloudFront with Origin Access Control and the bucket itself private).
Both: ACLs disabled (bucket-owner-enforced), TLS required, versioning on. Do
not apply an expiry rule to ordered artwork; an operational cleanup job may
separately remove unreferenced generation drafts after a safe retention
period.

**CJ images.** `tasks.catalogue_image_tasks.mirror_catalogue_images` (every 15
minutes, on the product taskiq scheduler) copies every CJ image still in use
into the catalogue bucket and rewrites the rows to the copy's key; the
supplier sync then keeps writing the key (`catalogue_image_mirrors`). Only
HTTPS URLs on `*.cjdropshipping.com` are fetched, without following
redirects. An image that cannot be copied stays served from CJ, is retried
with a growing delay and given up on after `CATALOGUE_IMAGE_MIRROR_MAX_ATTEMPTS`.

## Which artwork is ordered

order_service holds the reference to a print file while this service owns the
object, so nothing local could tell a paid order's artwork from an abandoned
preview. The `retained_artwork` table is that link. On `order.confirmed`,
order_service emits `artwork.retained` with the keys of every custom line;
`order.cancelled` emits `artwork.released`. Both arrive on
`product.artwork.events.queue` and are applied by `ArtworkAssetService`.

**A cleanup job must call `RetainedArtworkRepository.is_key_retained(key)` and
skip any key it reports, however old the object is.** One live hold from any
order is enough to keep the file.

## Serving a print file to the operator

`POST /api/v1/artwork/download-link` exchanges a signed manifest for a
short-lived download URL — a presigned S3 GET with an attachment disposition,
or a `/media/...` path under the local backend. The manifest is the credential:
only a caller holding the manifest this service issued at generation time can
obtain the object, so the key alone is never enough. The route is restricted to
internal callers and is deliberately not exposed through the API gateway;
order_service calls it on behalf of the operator working the production queue.

The default maximum garment area is 15 x 18 inches. Assets must contain at
least 2250 x 2700 pixels (150 effective DPI at that size); the generator asks
for native 4K output and the service deliberately does not upscale small
images. PNG files are tagged at 300 DPI for printer software, while order-time
effective DPI is calculated from actual pixels and the selected placement.
