using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression);
    void VisitLiteralBoolExpression(LiteralBoolExpressionNode literalBoolExpressionNode);
    void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode);
    void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode);
    void VisitIdentifierExpression(IdentifierExpressionNode node);
    void VisitVarAssignmentStatement(VarAssignmentStatementNode node);
    void VisitNamedTypeNode(NamedTypeNode node);
    void VisitBlockStatement(BlockStatementNode node);
    void VisitFunctionDeclarationNode(FunctionDeclarationNode node);
    void VisitReturnStatementNode(ReturnStatementNode node);
}