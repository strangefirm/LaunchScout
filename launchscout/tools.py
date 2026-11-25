"""Tools that give the agents real access to the web and the file system."""
from crewai_tools import FileWriterTool, ScrapeWebsiteTool, SerperDevTool

from launchscout.config import OUTPUT_DIR


def search_tool() -> SerperDevTool:
    """Google search via Serper. Returns titles, links and snippets."""
    return SerperDevTool(n_results=8)


def scrape_tool() -> ScrapeWebsiteTool:
    """Reads the text of any web page the agent passes a URL for."""
    return ScrapeWebsiteTool()


def file_writer_tool() -> FileWriterTool:
    """Writes files, locked to the outputs/ folder."""
    return FileWriterTool(base_dir=str(OUTPUT_DIR))
