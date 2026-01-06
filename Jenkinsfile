// codectl version : 1.5.2
pipeline {
    /* In this step, you can define where your job can run.
    
     * In more advanced usages, you can have the entire build be run inside of a Docker containers
     * in order to use custom tools not natively supported by Jenkins.
    
     */
    agent any
    
    
    /*
    * Uncomment this section if you want to use specific deploy or artifact record for build
    * 'codectl get deploy' and 'codectl get artifact' gives you the list of respective IDs
    environment{
        DEPLOY_ID=""
        ARTIFACT_ID=""
    }
    */


    stages {

        /* This stage runs pre-build tasks, such as loading variables or outputing start notifications
         */
        stage ('Pre-Build') {
            steps {
                notifyBuildStart()
                }
        }/* In this stage, the code is being built/compiled, and the Docker image is being created and tagged.
         * Tests shouldn't been run in this stage, in order to speed up time to deployment.
         */   
        stage ('Build') {
            steps {
                
				// Run the docker build command and tag the image with the git commit ID
				dockerBuild()
            }

        }

        

        
        /* In this stage, built images are being pushed
         */
        stage ('Push') {
            steps {
			// Authenticates with your remote Docker Repository, and pushes the value of "$DOCKER_PUSH_TAG-environment_name" for all the environments provided as the parameter,
			// By default all the dev environments with "autoDeploy" marked as true is used
			// which will exist if you used 'tagDocker' to tag your image, or set it manually. If you have done neither,
			// you can instead define your image using the 'image' parameter.
			// You can change the credentials used by using the 'authId' parameter.
			// The difference between this, and 'docker push $image', is that this handles 'docker login' for you.
			dockerPush()
			// Send Webex notification about docker push event status to the Webex room defined ID in the software details, using the
			// 'CoDE:ContainerHub' bot
			notifyDocker()
            }
        }


        

        /* In this stage, we're running several different sub-stages in parallel. This speeds up job time by running many different
         * steps (that don't necessarily need to be run in sequence) at the same time, speeding up your job runtime.
         */
		stage ('QA') {
            // Run these stages in parallel
            parallel {

                /* This stage simply runs your Static Security Scan. Uncomment it and include your stack name to use it.
                 */
                stage ('Static Security Scan') {
                    steps {
                        // Behaves exactly like the Static Security Scan step you know and love in your Maven and Freestyle jobs.
                        scavaSecurityScan(webexTeamsId: "$WEBEX_TEAMS_ROOM_ID")
                    }
                }

                /* This steps runs your unit tests, and your SonarQube scan.
                 * This stage may vary heavily depending on your project language and structure.
                 */
                
                
                stage ('Test/Sonar') {
                    
					steps {
						// This specific examples expects that you have a Dockerfile.test that you build, then run to generate test results.
						// Since different projects can vary however, you should make sure you use the solution that works best for you.

                        // If you need to remove cached coverage on runs, uncomment the below line
                        // sh "rm .coverage .coverage.xml nosetests.xml | true"
						sh "rm -rf coverage.xml nosetests.xml .coverage kubelint.json kubelint.log Dockerlint.json lintresult.log"
						sh "docker build . -f Dockerfile.test -t node-test:${BUILD_ID}"

						sh '''docker run node-test:${BUILD_ID}'''
						// sh '''sed -i 's|filename="|filename="'"$(pwd)"'/|' coverage.xml'''
						
                                                echo "Starting Kube-linter....."
                                                sh 'docker run --rm -i -v "$(pwd)":/app stackrox/kube-linter lint /app/config/ --format=json > kubelint.json || exit 0'
                                                echo "Starting Docker Linter..."
                                                sh 'docker run --rm -i hadolint/hadolint /bin/hadolint --no-fail --verbose --format json - < Dockerfile > Dockerlint.json || exit 0' 
                                                echo "Starting Custom Linter..."
                                                sh 'docker run --rm -i -v "$(pwd)":/app containers.cisco.com/proseide/codeshift-linter:latest || exit 0'
						
						sonarScan('Sonar')
					}

					// Make test results visible in Jenkins UI if the install step completed successfully
					post {
						success {
							junit testResults: 'nosetests.xml', allowEmptyResults: true
						}
					}
                }
                
            }
        }

        stage ('Deploy All') {
            steps {
                triggerSpinnakerDevDeployment(
                    environments: [
                        'dev',
                    ],
                )
            }
        }
    }
    post {
        always {
            notifyBuildEnd()
        }
    }
}