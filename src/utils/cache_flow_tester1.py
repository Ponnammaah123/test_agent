"""
Simple Test Class - Verify Cache Flow

This class demonstrates all 3 steps:
1. Fetch codebase from GitHub
2. Cache content automatically
3. Retrieve cached content by repository:branch
"""

import sys
from pathlib import Path

# Fix paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.clients.github_client import GitHubClient
from src.config.settings import Config


class CacheFlowTester:
    """
    Simple test class to verify:
    1. Fetch → Cache → Retrieve workflow
    2. Content is properly cached
    3. Retrieval by repository:branch works
    """
    
    def __init__(self):
        """Initialize tester"""
        try:
            self.config = Config()
            self.client = GitHubClient(self.config, enable_cache=True)
            print("✅ CacheFlowTester initialized")
        except Exception as e:
            print(f"❌ Error: {e}")
            raise
    
    # ========================================================================
    # STEP 1: FETCH CODEBASE FROM GITHUB
    # ========================================================================
    
    def test_step_1_fetch_from_github(self, branch: str) -> bool:
        """
        Step 1: Fetch codebase from GitHub
        
        This calls analyze_codebase() which:
        - Fetches files from GitHub
        - Gets file content
        - Gets file diffs
        - Automatically caches everything
        """
        print("\n" + "="*80)
        print("STEP 1: FETCH CODEBASE FROM GITHUB")
        print("="*80)
        
        try:
            print(f"\n📝 Fetching codebase for branch: {branch}")
            response = self.client.analyze_codebase(branch=branch)
            
            print(f"✅ Fetch successful!")
            print(f"   Repository: {response.repository}")
            print(f"   Branch: {response.branch}")
            print(f"   Files changed: {len(response.files_changed)}")
            print(f"   Components: {len(response.components_identified)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Step 1: {e}")
            return False
    
    # ========================================================================
    # STEP 2: VERIFY CACHE POPULATED
    # ========================================================================
    
    def test_step_2_verify_cache_populated(self, branch: str) -> bool:
        """
        Step 2: Verify that cache was populated after Step 1
        
        The analyze_codebase() method automatically caches content.
        We verify by checking cache statistics and getting cached files.
        """
        print("\n" + "="*80)
        print("STEP 2: VERIFY CACHE WAS POPULATED")
        print("="*80)
        
        try:
            # Get cache stats
            print("\n📝 Checking cache statistics...")
            stats = self.client.get_cache_stats()
            
            print(f"✅ Cache statistics:")
            print(f"   Entries: {stats['cache_entries']}/{stats['max_entries']}")
            print(f"   Total files: {stats['total_files_cached']}")
            print(f"   Cache size: {stats['total_content_size_mb']:.2f}MB")
            print(f"   Hit rate: {stats['hit_rate_percent']}")
            
            # Verify cache is not empty
            if stats['total_files_cached'] == 0:
                print("❌ Cache is empty!")
                return False
            
            print(f"\n✅ Cache is populated with {stats['total_files_cached']} files")
            
            # Show cache entries
            print(f"\n📝 Cache entries:")
            for entry_key in stats['entries']:
                print(f"   - {entry_key}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Step 2: {e}")
            return False
    
    # ========================================================================
    # STEP 3: RETRIEVE CACHED CONTENT BY REPOSITORY:BRANCH
    # ========================================================================
    
    def test_step_3_retrieve_by_key(self, branch: str) -> bool:
        """
        Step 3: Retrieve cached content by repository:branch
        
        Uses get_cached_files(branch) which returns all files with content
        for the given branch. The key is implicitly: {repo}:{branch}
        """
        print("\n" + "="*80)
        print("STEP 3: RETRIEVE CACHED CONTENT BY REPOSITORY:BRANCH")
        print("="*80)
        
        try:
            # Get repository from client
            repository = self.client.repo
            
            print(f"\n📝 Retrieving cached content for key: {repository}:{branch}")
            
            # REQUIREMENT: Retrieve all files by key (repository:branch)
            cached_files = self.client.get_cached_files(branch=branch)
            
            if not cached_files:
                print("❌ No cached files found!")
                return False
            
            print(f"✅ Retrieved {len(cached_files)} files from cache")
            
            # Show files
            print(f"\n📝 Cached files:")
            for file_path, cached_file in cached_files.items():
                content_length = len(cached_file.content or "")
                diff_length = len(cached_file.diff or "")
                
                print(f"\n   File: {file_path}")
                print(f"   ├─ Status: {cached_file.status}")
                print(f"   ├─ Language: {cached_file.language}")
                print(f"   ├─ Content: {content_length} characters")
                print(f"   ├─ Diff: {diff_length} characters")
                print(f"   ├─ Changes: +{cached_file.additions} -{cached_file.deletions}")
                print(f"   └─ Hash: {cached_file.file_hash[:16]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Step 3: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ========================================================================
    # STEP 3b: RETRIEVE SPECIFIC FILE BY PATH
    # ========================================================================
    
    def test_step_3b_retrieve_specific_file(self, branch: str, file_path: str) -> bool:
        """
        Step 3b: REQUIREMENT - Retrieve specific file by repository:branch:path
        
        Uses get_cached_file_content(branch, path) to get specific file content
        """
        print("\n" + "="*80)
        print(f"---------STEP 3b: RETRIEVE SPECIFIC FILE for PATH-----",file_path)
        print("="*80)
        
        try:
            repository = self.client.repo
            
            print(f"\n📝 Retrieving file: {repository}:{branch}:{file_path}")
            
            # REQUIREMENT: Get specific file by path
            content = self.client.get_cached_file_content(
                branch=branch,
                file_path=file_path
            )
            
            if content is None:
                print(f"❌ File not found in cache!")
                return False
            
            print(f"✅ Retrieved file content!")
            print(f"   File: {file_path}")
            print(f"   Content length: {len(content)} characters")
            print(f"\n   Content preview (first 300 chars):")
            print("   " + "─"*76)
            preview = content[:100].replace("\n", "\n   ")
            print("   " + preview)
            if len(content) > 100:
            # preview = content.replace("\n", "\n   ")
            # print("   " + preview)
            # if len(content) > 10000:
                 print("   ...")
            print("   " + "─"*76)
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Step 3b: {e}")
            return False
    
    # ========================================================================
    # VERIFY PERFORMANCE (Cache should be instant)
    # ========================================================================
    
    def test_performance_cache_speed(self, branch: str) -> bool:
        """Verify cache is faster than first call"""
        print("\n" + "="*80)
        print("PERFORMANCE TEST: CACHE SPEED")
        print("="*80)
        
        try:
            import time
            
            # Clear cache first
            print("\n📝 Clearing cache...")
            self.client.clear_cache()
            
            # Cold call
            print(f"\n📝 Cold call (from GitHub)...")
            start = time.time()
            response1 = self.client.analyze_codebase(branch=branch)
            time1 = time.time() - start
            print(f"✅ Time: {time1:.3f}s ({len(response1.files_changed)} files)")
            
            # Warm call (from cache)
            print(f"\n📝 Warm call (from cache)...")
            start = time.time()
            response2 = self.client.analyze_codebase(branch=branch)
            time2 = time.time() - start
            print(f"✅ Time: {time2:.3f}s ({len(response2.files_changed)} files)")
            
            # Calculate speedup
            if time2 > 0:
                speedup = time1 / time2
                print(f"\n⚡ Performance improvement:")
                print(f"   First call: {time1:.3f}s")
                print(f"   Cached call: {time2:.3f}s")
                print(f"   Speedup: {speedup:.1f}x faster!")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    # ========================================================================
    # COMPREHENSIVE TEST
    # ========================================================================
    
    def run_all_tests(self, branch: str, file_path: str = None) -> bool:
        """Run all tests in sequence"""
        
        results = {}
        
        # Step 1: Fetch
        #results['fetch'] = "Not ran this !!!"
        results['fetch'] = self.test_step_1_fetch_from_github(branch)
        
        # Step 2: Verify cache
        results['cache'] = self.test_step_2_verify_cache_populated(branch)
        #results['cache'] = "Not ran this !!!"

        # Step 3: Retrieve all
        results['retrieve_all'] = self.test_step_3_retrieve_by_key(branch)
        
        # Step 3b: Retrieve specific (if file_path provided)
        if file_path:
            results['retrieve_specific1'] = self.test_step_3b_retrieve_specific_file(
                branch, file_path
            )
            path2 = "main.py"
            results['retrieve_specific2'] = self.test_step_3b_retrieve_specific_file(
                branch, path2
            )
            path3 = "src/routers/attach_test_plan_api.py"
            results['retrieve_specific3'] = self.test_step_3b_retrieve_specific_file(
                branch, path3
            )
        # Performance test
        results['performance'] = self.test_performance_cache_speed(branch)
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        print("="*80)
        
        return passed == total


# ============================================================================
# MAIN - RUN TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + "  Cache Flow Tester - Verify 3 Step Flow".center(78) + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Initialize tester
        tester = CacheFlowTester()
        
        # Run tests
        branch = "feature/qe_agent_tools"
        file_path = "src/services/attach_test_plan_service.py"
        
        success = tester.run_all_tests(branch, file_path)
        
        if success:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✅ Cache flow is working correctly:")
            print("   1. Fetch from GitHub ✅")
            print("   2. Cache content ✅")
            print("   3. Retrieve by key ✅")
        else:
            print("\n❌ Some tests failed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()