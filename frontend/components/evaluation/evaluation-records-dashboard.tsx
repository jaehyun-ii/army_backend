"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  FileText,
  Search,
  Filter,
  Eye,
  Download,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Calendar,
  Brain,
  Target,
  Award,
  Image as ImageIcon,
  Box,
  ExternalLink,
  Activity
} from "lucide-react"

interface EvaluationRecord {
  id: string
  name: string
  model: string
  modelType: string
  timestamp: string
  dataType: '2d' | '3d'
  normalDataset: {
    name: string
    imageCount: number
    ap50: number
    f1Score: number
    precision: number
    recall: number
  }
  adversarialDatasets: Array<{
    name: string
    attackMethod: string
    imageCount: number
    ap50: number
    f1Score: number
    precision: number
    recall: number
    performanceDrop: number
    successfulAttacks: number
  }>
  reliabilityLevel: 'high' | 'medium' | 'low'
  reliabilityScore: number
  totalImages: number
  successfulAttacks: number
  evaluationTime: string
  status: 'completed' | 'failed' | 'in_progress'
}

interface AttackImage {
  id: string
  originalImage: string
  attackedImage: string
  originalPrediction: string
  attackPrediction: string
  confidence: {
    original: number
    attacked: number
  }
  attackMethod: string
}

export function EvaluationRecordsDashboard() {
  const [activeTab, setActiveTab] = useState("all")
  const [selectedRecord, setSelectedRecord] = useState<EvaluationRecord | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [filterModel, setFilterModel] = useState("all")
  const [filterReliability, setFilterReliability] = useState("all")
  const [filterDataType, setFilterDataType] = useState("all")
  const [sortBy, setSortBy] = useState("timestamp")

  // 샘플 평가 기록 데이터
  const evaluationRecords: EvaluationRecord[] = [
    {
      id: "eval_2d_001",
      name: "YOLOv8 자동차 분류 종합 평가",
      model: "YOLOv8",
      modelType: "Object Detection",
      timestamp: "2024-01-15 14:30",
      dataType: '2d',
      normalDataset: {
        name: "자동차 분류 데이터셋",
        imageCount: 15847,
        ap50: 0.87,
        f1Score: 0.82,
        precision: 0.85,
        recall: 0.79
      },
      adversarialDatasets: [
        {
          name: "FGSM 공격",
          attackMethod: "FGSM",
          imageCount: 5000,
          ap50: 0.34,
          f1Score: 0.31,
          precision: 0.33,
          recall: 0.29,
          performanceDrop: 60.9,
          successfulAttacks: 3050
        },
        {
          name: "PGD 공격",
          attackMethod: "PGD",
          imageCount: 3000,
          ap50: 0.28,
          f1Score: 0.25,
          precision: 0.27,
          recall: 0.23,
          performanceDrop: 67.8,
          successfulAttacks: 2034
        }
      ],
      reliabilityLevel: 'medium',
      reliabilityScore: 65.2,
      totalImages: 23847,
      successfulAttacks: 5084,
      evaluationTime: "2시간 45분",
      status: 'completed'
    },
    {
      id: "eval_2d_002",
      name: "ResNet50 군사 장비 분류 평가",
      model: "ResNet50",
      modelType: "Classification",
      timestamp: "2024-01-14 10:15",
      dataType: '2d',
      normalDataset: {
        name: "군사 장비 데이터셋",
        imageCount: 8932,
        ap50: 0.91,
        f1Score: 0.88,
        precision: 0.90,
        recall: 0.86
      },
      adversarialDatasets: [
        {
          name: "PGD 공격",
          attackMethod: "PGD",
          imageCount: 4500,
          ap50: 0.45,
          f1Score: 0.42,
          precision: 0.44,
          recall: 0.40,
          performanceDrop: 50.5,
          successfulAttacks: 2275
        }
      ],
      reliabilityLevel: 'high',
      reliabilityScore: 78.8,
      totalImages: 13432,
      successfulAttacks: 2275,
      evaluationTime: "1시간 32분",
      status: 'completed'
    },
    {
      id: "eval_3d_001",
      name: "CARLA 도시 환경 객체 탐지 평가",
      model: "YOLOv8",
      modelType: "Object Detection",
      timestamp: "2024-01-16 09:15",
      dataType: '3d',
      normalDataset: {
        name: "CARLA 도시 환경",
        imageCount: 12000,
        ap50: 0.79,
        f1Score: 0.76,
        precision: 0.78,
        recall: 0.74
      },
      adversarialDatasets: [
        {
          name: "3D 패치 공격",
          attackMethod: "3D Patch",
          imageCount: 8000,
          ap50: 0.42,
          f1Score: 0.38,
          precision: 0.40,
          recall: 0.36,
          performanceDrop: 46.8,
          successfulAttacks: 3744
        }
      ],
      reliabilityLevel: 'high',
      reliabilityScore: 72.5,
      totalImages: 20000,
      successfulAttacks: 3744,
      evaluationTime: "3시간 12분",
      status: 'completed'
    },
    {
      id: "eval_3d_002",
      name: "Unity 군사 시뮬레이션 평가",
      model: "PointNet++",
      modelType: "3D Detection",
      timestamp: "2024-01-13 16:45",
      dataType: '3d',
      normalDataset: {
        name: "Unity 군사 시뮬레이션",
        imageCount: 6500,
        ap50: 0.83,
        f1Score: 0.80,
        precision: 0.82,
        recall: 0.78
      },
      adversarialDatasets: [
        {
          name: "날씨 변화 공격",
          attackMethod: "Weather Attack",
          imageCount: 4200,
          ap50: 0.51,
          f1Score: 0.48,
          precision: 0.50,
          recall: 0.46,
          performanceDrop: 38.6,
          successfulAttacks: 1620
        }
      ],
      reliabilityLevel: 'high',
      reliabilityScore: 81.2,
      totalImages: 10700,
      successfulAttacks: 1620,
      evaluationTime: "2시간 18분",
      status: 'completed'
    },
    {
      id: "eval_2d_003",
      name: "Detectron2 다중 객체 탐지 평가",
      model: "Detectron2",
      modelType: "Object Detection",
      timestamp: "2024-01-12 13:20",
      dataType: '2d',
      normalDataset: {
        name: "COCO 데이터셋",
        imageCount: 25000,
        ap50: 0.89,
        f1Score: 0.86,
        precision: 0.88,
        recall: 0.84
      },
      adversarialDatasets: [
        {
          name: "C&W 공격",
          attackMethod: "C&W",
          imageCount: 7500,
          ap50: 0.31,
          f1Score: 0.28,
          precision: 0.30,
          recall: 0.26,
          performanceDrop: 65.2,
          successfulAttacks: 4875
        }
      ],
      reliabilityLevel: 'low',
      reliabilityScore: 52.3,
      totalImages: 32500,
      successfulAttacks: 4875,
      evaluationTime: "4시간 55분",
      status: 'completed'
    },
    {
      id: "eval_3d_003",
      name: "VoxelNet 도로 환경 평가",
      model: "VoxelNet",
      modelType: "3D Detection",
      timestamp: "2024-01-11 08:30",
      dataType: '3d',
      normalDataset: {
        name: "KITTI 3D 데이터셋",
        imageCount: 15000,
        ap50: 0.75,
        f1Score: 0.71,
        precision: 0.74,
        recall: 0.68
      },
      adversarialDatasets: [
        {
          name: "기하학적 변형 공격",
          attackMethod: "Geometric Transform",
          imageCount: 9000,
          ap50: 0.38,
          f1Score: 0.34,
          precision: 0.36,
          recall: 0.32,
          performanceDrop: 49.3,
          successfulAttacks: 4437
        }
      ],
      reliabilityLevel: 'medium',
      reliabilityScore: 68.9,
      totalImages: 24000,
      successfulAttacks: 4437,
      evaluationTime: "5시간 23분",
      status: 'failed'
    }
  ]

  const filteredRecords = evaluationRecords.filter(record => {
    const matchesSearch = record.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         record.model.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesModel = filterModel === "all" || record.model === filterModel
    const matchesReliability = filterReliability === "all" || record.reliabilityLevel === filterReliability
    const matchesDataType = filterDataType === "all" || record.dataType === filterDataType
    const matchesTab = activeTab === "all" ||
                      (activeTab === "2d" && record.dataType === "2d") ||
                      (activeTab === "3d" && record.dataType === "3d") ||
                      (activeTab === "completed" && record.status === "completed") ||
                      (activeTab === "failed" && record.status === "failed")

    return matchesSearch && matchesModel && matchesReliability && matchesDataType && matchesTab
  })

  const getReliabilityColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-green-400'
      case 'medium': return 'text-yellow-400'
      case 'low': return 'text-red-400'
      default: return 'text-slate-400'
    }
  }

  const getReliabilityBadge = (level: string) => {
    switch (level) {
      case 'high': return 'bg-green-900/40 text-green-300 border-green-500/40'
      case 'medium': return 'bg-yellow-900/40 text-yellow-300 border-yellow-500/40'
      case 'low': return 'bg-red-900/40 text-red-300 border-red-500/40'
      default: return 'bg-slate-900/40 text-slate-300 border-slate-500/40'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-900/40 text-green-300 border-green-500/40'
      case 'failed': return 'bg-red-900/40 text-red-300 border-red-500/40'
      case 'in_progress': return 'bg-blue-900/40 text-blue-300 border-blue-500/40'
      default: return 'bg-slate-900/40 text-slate-300 border-slate-500/40'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'failed': return <XCircle className="w-4 h-4 text-red-400" />
      case 'in_progress': return <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      default: return <AlertTriangle className="w-4 h-4 text-slate-400" />
    }
  }

  const totalRecords = evaluationRecords.length
  const completedRecords = evaluationRecords.filter(r => r.status === 'completed').length
  const failedRecords = evaluationRecords.filter(r => r.status === 'failed').length
  const inProgressRecords = evaluationRecords.filter(r => r.status === 'in_progress').length
  const averageReliability = evaluationRecords.length > 0
    ? (evaluationRecords.reduce((acc, r) => acc + r.reliabilityScore, 0) / evaluationRecords.length).toFixed(1)
    : '0'

  return (
    <div className="h-full flex flex-col gap-2">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-800/80 to-slate-900/80 rounded-xl p-3 border border-white/10 shadow-xl flex-shrink-0">
        <div className="flex-shrink-0">
          <h1 className="text-lg lg:text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-6 h-6 text-cyan-400" />
            신뢰성 평가 기록 관리
          </h1>
          <p className="text-xs text-slate-400">2D/3D AI 모델 신뢰성 평가 결과 및 기록 통합 관리</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 space-y-6 overflow-auto">
      {/* 통계 및 필터 */}
      <Card className="bg-slate-800/50 border-white/10">
        <CardContent className="pt-6">
          {/* 통계 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-blue-400" />
                <span className="text-slate-400 text-sm">총 평가</span>
              </div>
              <div className="text-2xl font-bold text-white">{totalRecords}</div>
            </div>
            <div className="bg-slate-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-slate-400 text-sm">완료</span>
              </div>
              <div className="text-2xl font-bold text-green-400">{completedRecords}</div>
            </div>
            <div className="bg-slate-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-yellow-400" />
                <span className="text-slate-400 text-sm">진행 중</span>
              </div>
              <div className="text-2xl font-bold text-yellow-400">{inProgressRecords}</div>
            </div>
            <div className="bg-slate-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-purple-400" />
                <span className="text-slate-400 text-sm">평균 신뢰도</span>
              </div>
              <div className="text-2xl font-bold text-purple-400">{averageReliability}%</div>
            </div>
          </div>

          {/* 필터 및 검색 */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
              <Input
                placeholder="평가 이름 또는 모델 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-slate-700/50 border-white/10 text-white pl-10"
              />
            </div>
            <Select value={filterModel} onValueChange={setFilterModel}>
              <SelectTrigger className="bg-slate-700/50 border-white/10 text-white">
                <SelectValue placeholder="모델 필터" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">모든 모델</SelectItem>
                <SelectItem value="YOLOv8">YOLOv8</SelectItem>
                <SelectItem value="ResNet50">ResNet50</SelectItem>
                <SelectItem value="Detectron2">Detectron2</SelectItem>
                <SelectItem value="PointNet++">PointNet++</SelectItem>
                <SelectItem value="VoxelNet">VoxelNet</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterReliability} onValueChange={setFilterReliability}>
              <SelectTrigger className="bg-slate-700/50 border-white/10 text-white">
                <SelectValue placeholder="신뢰성 필터" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">모든 등급</SelectItem>
                <SelectItem value="high">높음</SelectItem>
                <SelectItem value="medium">보통</SelectItem>
                <SelectItem value="low">낮음</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterDataType} onValueChange={setFilterDataType}>
              <SelectTrigger className="bg-slate-700/50 border-white/10 text-white">
                <SelectValue placeholder="데이터 타입" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">모든 타입</SelectItem>
                <SelectItem value="2d">2D 이미지</SelectItem>
                <SelectItem value="3d">3D 시뮬레이션</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              내보내기
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 탭 및 기록 목록 */}
      <Card className="bg-slate-800/50 border-white/10">
        <CardHeader className="pb-3">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-5 bg-slate-800/50">
              <TabsTrigger value="all" className="text-white">전체</TabsTrigger>
              <TabsTrigger value="2d" className="text-white flex items-center gap-2">
                <ImageIcon className="w-4 h-4" />
                2D
              </TabsTrigger>
              <TabsTrigger value="3d" className="text-white flex items-center gap-2">
                <Box className="w-4 h-4" />
                3D
              </TabsTrigger>
              <TabsTrigger value="completed" className="text-white">완료</TabsTrigger>
              <TabsTrigger value="failed" className="text-white">실패</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-y-auto">
            <div className="space-y-2">
              {filteredRecords.map((record) => (
                <Card key={record.id} className="bg-slate-800/50 border-white/10 p-4 hover:bg-slate-800/70 transition-colors">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(record.status)}
                        <div>
                          <h4 className="text-white font-medium">{record.name}</h4>
                          <div className="flex items-center gap-4 text-sm text-slate-400">
                            <span className="flex items-center gap-1">
                              <Brain className="w-3 h-3" />
                              {record.model}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {record.timestamp}
                            </span>
                            <span className="flex items-center gap-1">
                              {record.dataType === '2d' ? <ImageIcon className="w-3 h-3" /> : <Box className="w-3 h-3" />}
                              {record.dataType.toUpperCase()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={getReliabilityBadge(record.reliabilityLevel)}>
                          {record.reliabilityLevel.toUpperCase()}
                        </Badge>
                        <Badge className={getStatusBadge(record.status)}>
                          {record.status === 'completed' ? '완료' : record.status === 'failed' ? '실패' : '진행중'}
                        </Badge>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-slate-400">신뢰성 점수:</span>
                        <span className={`ml-2 font-semibold ${getReliabilityColor(record.reliabilityLevel)}`}>
                          {record.reliabilityScore}%
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400">총 이미지:</span>
                        <span className="text-white ml-2 font-semibold">
                          {record.totalImages.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400">공격 성공:</span>
                        <span className="text-red-400 ml-2 font-semibold">
                          {record.successfulAttacks.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400">평가 시간:</span>
                        <span className="text-white ml-2 font-semibold">
                          {record.evaluationTime}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/10">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400 text-sm">정상 데이터:</span>
                        <span className="text-white text-sm">{record.normalDataset.name}</span>
                        <span className="text-slate-400 text-sm">
                          (AP50: {(record.normalDataset.ap50 * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setSelectedRecord(record)
                            setShowDetailModal(true)
                          }}
                          className="text-xs"
                        >
                          <Eye className="w-3 h-3 mr-1" />
                          상세보기
                        </Button>
                        <Button size="sm" variant="outline" className="text-xs">
                          <Download className="w-3 h-3 mr-1" />
                          다운로드
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

        {/* 상세 정보 모달 */}
        <Dialog  open={showDetailModal} onOpenChange={setShowDetailModal}>
        <DialogContent className="bg-slate-900 border-white/20 !max-w-[90vw] !w-auto sm:!max-w-[90vw]">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-400" />
              {selectedRecord?.name}
            </DialogTitle>
            <DialogDescription className="text-slate-400">
              상세 평가 결과 및 성능 분석
            </DialogDescription>
          </DialogHeader>

          {selectedRecord && (
            <div className="space-y-4 min-w-[800px]">
              {/* 기본 정보 */}
              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-slate-800/50 border-white/10">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-white text-sm">모델 정보</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">모델:</span>
                      <span className="text-white">{selectedRecord.model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">타입:</span>
                      <span className="text-white">{selectedRecord.modelType}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">데이터 타입:</span>
                      <span className="text-white">{selectedRecord.dataType.toUpperCase()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">평가 시간:</span>
                      <span className="text-white">{selectedRecord.evaluationTime}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-800/50 border-white/10">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-white text-sm">신뢰성 분석</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">신뢰성 점수:</span>
                      <span className={`font-semibold ${getReliabilityColor(selectedRecord.reliabilityLevel)}`}>
                        {selectedRecord.reliabilityScore}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">신뢰성 등급:</span>
                      <Badge className={getReliabilityBadge(selectedRecord.reliabilityLevel)}>
                        {selectedRecord.reliabilityLevel.toUpperCase()}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">총 이미지:</span>
                      <span className="text-white">{selectedRecord.totalImages.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">공격 성공:</span>
                      <span className="text-red-400">{selectedRecord.successfulAttacks.toLocaleString()}</span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* 정상 데이터셋 성능 */}
              <Card className="bg-slate-800/50 border-white/10">
                <CardHeader className="pb-3">
                  <CardTitle className="text-white text-sm">정상 데이터셋 성능</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-slate-400">데이터셋</TableHead>
                        <TableHead className="text-slate-400">이미지 수</TableHead>
                        <TableHead className="text-slate-400">AP50</TableHead>
                        <TableHead className="text-slate-400">F1 Score</TableHead>
                        <TableHead className="text-slate-400">Precision</TableHead>
                        <TableHead className="text-slate-400">Recall</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow>
                        <TableCell className="text-white">{selectedRecord.normalDataset.name}</TableCell>
                        <TableCell className="text-white">{selectedRecord.normalDataset.imageCount.toLocaleString()}</TableCell>
                        <TableCell className="text-green-400">{(selectedRecord.normalDataset.ap50 * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-green-400">{(selectedRecord.normalDataset.f1Score * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-green-400">{(selectedRecord.normalDataset.precision * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-green-400">{(selectedRecord.normalDataset.recall * 100).toFixed(1)}%</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* 적대적 공격 결과 */}
              <Card className="bg-slate-800/50 border-white/10">
                <CardHeader className="pb-3">
                  <CardTitle className="text-white text-sm">적대적 공격 결과</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-slate-400">패치 생성 방법</TableHead>
                        <TableHead className="text-slate-400">이미지 수</TableHead>
                        <TableHead className="text-slate-400">AP50</TableHead>
                        <TableHead className="text-slate-400">F1 Score</TableHead>
                        <TableHead className="text-slate-400">성능 저하</TableHead>
                        <TableHead className="text-slate-400">공격 성공</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedRecord.adversarialDatasets.map((dataset, index) => (
                        <TableRow key={index}>
                          <TableCell className="text-white">{dataset.attackMethod}</TableCell>
                          <TableCell className="text-white">{dataset.imageCount.toLocaleString()}</TableCell>
                          <TableCell className="text-red-400">{(dataset.ap50 * 100).toFixed(1)}%</TableCell>
                          <TableCell className="text-red-400">{(dataset.f1Score * 100).toFixed(1)}%</TableCell>
                          <TableCell className="text-red-400 flex items-center gap-1">
                            <TrendingDown className="w-4 h-4" />
                            {dataset.performanceDrop.toFixed(1)}%
                          </TableCell>
                          <TableCell className="text-red-400">{dataset.successfulAttacks.toLocaleString()}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </DialogContent>
      </Dialog>
      </div>
    </div>
  )
}