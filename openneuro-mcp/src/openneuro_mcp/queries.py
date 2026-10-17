"""GraphQL documents for the OpenNeuro API (https://openneuro.org/crn/graphql).

Field names follow the official schema in
OpenNeuroOrg/openneuro: packages/openneuro-server/src/graphql/schema/.
Every document here is validated against tests/openneuro_schema.graphql.
"""

SUMMARY_FIELDS = """
  modalities
  primaryModality
  secondaryModalities
  subjects
  sessions
  tasks
  size
  totalFiles
  dataProcessed
"""

METADATA_FIELDS = """
  dxStatus
  species
  studyDomain
  studyDesign
  studyLongitudinal
  ages
  modalities
  associatedPaperDOI
  openneuroPaperDOI
  seniorAuthor
  grantFunderName
  trialCount
  tasksCompleted
  dataProcessed
  syntheticDataset
"""

SEARCH_DATASETS = f"""
query SearchDatasets($query: DatasetSearchInput!, $first: Int, $after: String) {{
  advancedSearch(query: $query, first: $first, after: $after) {{
    pageInfo {{ hasNextPage endCursor count }}
    edges {{
      node {{
        id
        name
        created
        publishDate
        metadata {{ dxStatus species studyDomain associatedPaperDOI }}
        latestSnapshot {{
          tag
          summary {{ {SUMMARY_FIELDS} }}
        }}
      }}
    }}
  }}
}}
"""

SNAPSHOT_FIELDS = f"""
  tag
  created
  size
  readme
  description {{
    Name
    BIDSVersion
    License
    Authors
    Funding
    ReferencesAndLinks
    DatasetDOI
    DatasetType
    EthicsApprovals
    HowToAcknowledge
  }}
  summary {{
    {SUMMARY_FIELDS}
    subjectMetadata {{ participantId age sex group }}
  }}
  related {{ id relation kind description }}
"""

GET_DATASET = f"""
query GetDataset($id: ID!) {{
  dataset(id: $id) {{
    id
    name
    created
    publishDate
    snapshots {{ tag created }}
    derivatives {{ name s3Url dataladUrl }}
    metadata {{ {METADATA_FIELDS} }}
    latestSnapshot {{ {SNAPSHOT_FIELDS} }}
  }}
}}
"""

GET_SNAPSHOT = f"""
query GetSnapshot($id: ID!, $tag: String!) {{
  snapshot(datasetId: $id, tag: $tag) {{ {SNAPSHOT_FIELDS} }}
}}
"""

LATEST_TAG = """
query LatestTag($id: ID!) {
  dataset(id: $id) {
    id
    latestSnapshot { tag }
  }
}
"""

LIST_FILES = """
query ListFiles($id: ID!, $tag: String!, $tree: String) {
  snapshot(datasetId: $id, tag: $tag) {
    tag
    files(tree: $tree) { id filename size annexed directory urls }
  }
}
"""

DOWNLOAD_INFO = """
query DownloadInfo($id: ID!) {
  dataset(id: $id) {
    id
    name
    derivatives { name s3Url dataladUrl }
    latestSnapshot {
      tag
      size
      summary { modalities subjects totalFiles size dataProcessed }
    }
  }
}
"""

CENSUS_PAGE = """
query CensusPage($first: Int, $after: String, $modality: String, $withGroups: Boolean!) {
  datasets(first: $first, after: $after, modality: $modality, filterBy: { public: true }) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        created
        metadata {
          dxStatus
          species
          studyDomain
          ages
          associatedPaperDOI
          syntheticDataset
        }
        latestSnapshot {
          tag
          summary {
            modalities
            primaryModality
            subjects
            tasks
            size
            dataProcessed
            subjectMetadata @include(if: $withGroups) { participantId age sex group }
          }
        }
      }
    }
  }
}
"""

PUBLIC_METADATA = f"""
query PublicMetadata {{
  publicMetadata {{
    datasetId
    datasetName
    latestSnapshotCreatedAt
    {METADATA_FIELDS}
  }}
}}
"""

PARTICIPANT_COUNT = """
query ParticipantCount($modality: String) {
  participantCount(modality: $modality)
}
"""

ALL_DOCUMENTS = {
    "SEARCH_DATASETS": SEARCH_DATASETS,
    "GET_DATASET": GET_DATASET,
    "GET_SNAPSHOT": GET_SNAPSHOT,
    "LATEST_TAG": LATEST_TAG,
    "LIST_FILES": LIST_FILES,
    "DOWNLOAD_INFO": DOWNLOAD_INFO,
    "CENSUS_PAGE": CENSUS_PAGE,
    "PUBLIC_METADATA": PUBLIC_METADATA,
    "PARTICIPANT_COUNT": PARTICIPANT_COUNT,
}
