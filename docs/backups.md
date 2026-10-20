# Backups (real business: Cuci-Cuci Senawang)

The `cuci-cuci` database (Neon, Postgres 18) is copied every night to a private Cloud Storage bucket. Neon's own history only reaches back a short time; this copy does not depend on Neon at all.

| Piece | What |
|---|---|
| Schedule | Cloud Scheduler `cc-backup-nightly`, 03:30 Malaysia time, runs as `backup-scheduler` (may only start this job) |
| Job | Cloud Run job `cc-backup`, defined in [`deploy/cc-backup-job.yaml`](../deploy/cc-backup-job.yaml) |
| Tool | `pg_dump` 18 from the official image, mirrored to Artifact Registry (`kilau/postgres:18-bookworm`) |
| Where | `gs://kilau-assistant-cc-backups/cuci-cuci-<UTC time>.dump`, Singapore, public access blocked |
| Kept | 30 days (a bucket lifecycle rule deletes older copies) |
| Permissions | The job runs as `cc-backup`: it can read the `cc-database-url` secret and **add** files to the bucket. It can't change or delete a backup, so a mistake (or an attacker using the app's credentials) can't wipe the history. |

Each run dumps the database in `pg_dump`'s compressed custom format, checks the archive can be read (`pg_restore --list`), then copies it to the bucket. A failed run shows as a failed execution of `cc-backup` in the Cloud Run console.

## Check the backups

```bash
gcloud storage ls -l gs://kilau-assistant-cc-backups/
gcloud run jobs executions list --job cc-backup --region asia-southeast1 --limit 5
```

Take one now (e.g. before a risky change):

```bash
gcloud run jobs execute cc-backup --region asia-southeast1 --wait
```

## Restore

Practise on a throwaway database first; only restore over the live one if it is really lost or broken.

1. Download the copy you want:

   ```bash
   gcloud storage cp gs://kilau-assistant-cc-backups/cuci-cuci-2026-10-20T083542Z.dump backup.dump
   ```

2. **Test restore** (local Docker, Postgres 18 with pgvector):

   ```bash
   docker run -d --name restore-test -e POSTGRES_PASSWORD=restoretest -v "$PWD:/b" pgvector/pgvector:pg18
   docker exec restore-test pg_restore -U postgres -d postgres --no-owner --no-privileges /b/backup.dump
   docker exec restore-test psql -U postgres -c "select count(*) from orders"
   docker rm -f restore-test
   ```

3. **Real restore:** create a new, empty database (e.g. a new branch or database in the Neon project), restore into it with `pg_restore --no-owner --no-privileges -d "<its direct connection string>" backup.dump`, check it, then point the `cc-database-url` secret at it and redeploy `cuci-cuci`. Restoring into a new database, instead of over the old one, keeps the broken copy for investigation and makes the switch reversible.

Delete downloaded copies when done: they contain customers' names, phone numbers and payments.

## Set up from scratch

```bash
P=kilau-assistant; B=kilau-assistant-cc-backups
gcloud storage buckets create gs://$B --location asia-southeast1 --uniform-bucket-level-access --public-access-prevention
echo '{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}' > lifecycle.json
gcloud storage buckets update gs://$B --lifecycle-file=lifecycle.json

gcloud iam service-accounts create cc-backup
gcloud secrets add-iam-policy-binding cc-database-url --member serviceAccount:cc-backup@$P.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor
gcloud storage buckets add-iam-policy-binding gs://$B --member serviceAccount:cc-backup@$P.iam.gserviceaccount.com --role roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding gs://$B --member serviceAccount:cc-backup@$P.iam.gserviceaccount.com --role roles/storage.objectViewer

docker pull postgres:18-bookworm
docker tag postgres:18-bookworm asia-southeast1-docker.pkg.dev/$P/kilau/postgres:18-bookworm
docker push asia-southeast1-docker.pkg.dev/$P/kilau/postgres:18-bookworm
gcloud run jobs replace deploy/cc-backup-job.yaml --region asia-southeast1

gcloud iam service-accounts create backup-scheduler
gcloud run jobs add-iam-policy-binding cc-backup --region asia-southeast1 --member serviceAccount:backup-scheduler@$P.iam.gserviceaccount.com --role roles/run.invoker
gcloud scheduler jobs create http cc-backup-nightly --location asia-southeast1 \
  --schedule "30 3 * * *" --time-zone Asia/Kuala_Lumpur --http-method POST \
  --uri "https://run.googleapis.com/v2/projects/$P/locations/asia-southeast1/jobs/cc-backup:run" \
  --oauth-service-account-email backup-scheduler@$P.iam.gserviceaccount.com \
  --oauth-token-scope https://www.googleapis.com/auth/cloud-platform
```

If Neon moves to a newer Postgres major version, mirror the matching `postgres:<version>-bookworm` image and update the job: `pg_dump` must be at least the server's version.
