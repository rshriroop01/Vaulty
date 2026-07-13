/**
 * GENERATED FILE — do not edit by hand.
 * Regenerate with `make types` (API must be running): reflects /api/v1/openapi.json.
 * This placeholder is committed so the path alias resolves before first generation.
 */
export interface paths {
  "/api/v1/meta/version": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["VersionResponse"];
          };
        };
      };
    };
  };
}

export interface components {
  schemas: {
    VersionResponse: {
      name: string;
      version: string;
      environment: string;
      api_version: string;
    };
  };
}
