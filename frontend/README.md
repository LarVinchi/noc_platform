# NOC frontend

React/Vite operating console. See the root README for the complete preview.

- `npm ci`, then `npm run dev`: local development.
- `npm run lint` and `npm run build`: validation.
- Docker target `development`: Vite and hot reload.
- Docker target `production` (default): compiled assets served by non-root Nginx
  on port 8080. No Node, source tree or node_modules in the final image.

Production uses same-origin `/api` and authenticated `/static` proxying. The Entra
redirect page is a required build entry; keep `redirect.html`. Deployment and
remaining release gates are documented in `../docs/container-builds.md`.
