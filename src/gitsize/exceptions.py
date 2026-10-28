"""Custom exception hierarchy for GitSize."""


class GitSizeError(Exception):
    """Base exception for all GitSize domain errors."""
    pass


class GitNotFoundError(GitSizeError):
    """Raised when the git executable is not available on PATH."""
    pass


class NotAGitRepositoryError(GitSizeError):
    """Raised when the specified path does not belong to a valid Git repository."""
    pass


class EmptyRepositoryError(GitSizeError):
    """Raised when a Git operation requires commits but repository has none."""
    pass


class ReportExistsError(GitSizeError):
    """Raised when an output report file already exists and overwrite was not permitted."""
    pass


class ScanError(GitSizeError):
    """Raised when a fatal filesystem or scanning error occurs."""
    pass
