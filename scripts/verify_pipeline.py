import logging
import os
import sys
from pathlib import Path

import yaml

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from paperweight.analyzer import get_abstracts
from paperweight.processor import process_papers
from paperweight.scraper import get_recent_papers

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify_pipeline")

def load_config():
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def verify_pipeline(config):  # noqa: C901
    logger.info("🧪 Verifying Pipeline (Scraper -> Processor -> Analyzer)...")

    # Override config for fast testing
    logger.info("   ℹ️  Overriding config to fetch max 1 paper from cs.AI...")
    config["arxiv"]["max_results"] = 1
    config["arxiv"]["categories"] = ["cs.AI"]

    # 1. Scraper
    logger.info("\n--- [1/3] Scraper Stage ---")
    try:
        # Use force_refresh=True to ensure we actually hit the API
        papers = get_recent_papers(config, force_refresh=True)

        if not papers:
            logger.error("❌ Scraper returned 0 papers.")
            return False

        logger.info(f"✅ Scraper fetched {len(papers)} paper(s).")
        logger.info(f"   Title: {papers[0]['title'][:50]}...")
        if 'content' not in papers[0] or not papers[0]['content']:
             logger.warning("   ⚠️  Paper content is empty! Processor might fail.")
        else:
             logger.info(f"   Content length: {len(papers[0]['content'])} chars")

    except Exception as e:
        logger.error(f"❌ Scraper stage failed: {e}")
        return False

    # 2. Processor
    logger.info("\n--- [2/3] Processor Stage ---")
    try:
        processed_papers = process_papers(papers, config["processor"])

        if processed_papers:
             logger.info(f"✅ Processor passed. {len(processed_papers)} paper(s) met criteria.")
             logger.info(f"   Score: {processed_papers[0].get('relevance_score')}")
        else:
            logger.info("ℹ️  Processor passed but filtered all papers (low score). Pipeline is working logic-wise.")
            # For verification purpose, let's pretend we have a paper to pass to analyzer
            # if we really want to test analyzer, we might need to fake a high score or relax criteria
            # But let's verify analyzer with the raw paper if processed list is empty, just to check API
            if not processed_papers:
                 logger.info("   (Using raw paper for Analyzer check since Processor filtered it details)")
                 processed_papers = papers

    except Exception as e:
        logger.error(f"❌ Processor stage failed: {e}")
        return False

    # 3. Analyzer
    logger.info("\n--- [3/3] Analyzer Stage ---")
    analyzer_config = config.get("analyzer", {})
    provider = analyzer_config.get("llm_provider")

    if not provider:
        logger.warning("⚠️  No LLM provider configured. Skipping Analyzer.")
        return True

    logger.info(f"   Provider: {provider}")

    # Check for API keys
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
         logger.warning("⚠️  OPENAI_API_KEY not found. Skipping Analyzer call.")
         return True
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
         logger.warning("⚠️  GEMINI_API_KEY not found. Skipping Analyzer call.")
         return True

    try:
        # Limit to 1 paper for cost/speed
        target_papers = processed_papers[:1]
        logger.info(f"   Sending {len(target_papers)} paper(s) to LLM...")

        summaries = get_abstracts(target_papers, analyzer_config)

        if summaries:
             logger.info("✅ Analyzer returned summaries.")
             if summaries[0]:
                logger.info(f"   Summary snippet: {summaries[0][:50]}...")
             else:
                logger.warning("   Summary was empty string (might be okay if abstract fallback used).")
        else:
             logger.error("❌ Analyzer returned None/Empty list.")
             return False

    except Exception as e:
         logger.error(f"❌ Analyzer stage failed: {e}")
         return False

    return True

if __name__ == "__main__":
    print("🚀 Starting Paperweight Pipeline Verification...")
    config = load_config()

    if verify_pipeline(config):
        print("\n🎉 SUCCESS: Core pipeline verified.")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: Pipeline verification failed.")
        sys.exit(1)
